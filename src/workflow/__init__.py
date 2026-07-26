"""
Workflow module: Orchestrates the flow of data between User, Memory, Plugins, and Model Router.

The Workflow class is the central coordinator:
  1. Receives user input
  2. Saves to Memory
  3. Loads conversation context from Memory
  4. Checks if input matches a Plugin (if so, executes plugin directly)
  5. Sends to Model Router with context
  6. Saves assistant response to Memory
  7. Returns result

Usage:
    workflow = Workflow(memory, model_router, plugin_loader)
    result = workflow.process("Hello!", session_id="abc123")
    print(result.response.text)
"""

import time
from dataclasses import dataclass, field
from typing import Optional

from src.core import (
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
    PluginExecutionError,
    setup_logger,
    truncate_text,
)
from src.core.cache import SimpleTTLCache, make_knowledge_cache_key
from src.memory import Memory
from src.model_router import ModelResponse, ModelRouter
from src.plugin import PluginLoader, PluginResult

logger = setup_logger("workflow")


# ============================================================
# Data Models
# ============================================================


@dataclass
class WorkflowResult:
    """
    Result of a single workflow execution cycle.

    Attributes:
        input: The original user input
        response: ModelResponse from the LLM (None if plugin was used)
        plugin_result: PluginResult if a plugin was executed (None if LLM was used)
        context_used: Number of context messages sent to the model
        latency_ms: Total execution time in milliseconds
        source: "llm" or "plugin"
        session_id: The session ID used
    """

    input: str
    response: Optional[ModelResponse] = None
    plugin_result: Optional[PluginResult] = None
    context_used: int = 0
    latency_ms: float = 0.0
    source: str = "llm"
    session_id: str = ""

    @property
    def output_text(self) -> str:
        """Get the human-readable output text."""
        if self.source == "plugin" and self.plugin_result:
            return self.plugin_result.output
        if self.response:
            return self.response.text
        return ""

    @property
    def success(self) -> bool:
        """Whether the workflow execution succeeded."""
        if self.source == "plugin" and self.plugin_result:
            return self.plugin_result.success
        return self.response is not None

    def __repr__(self) -> str:
        preview = truncate_text(self.output_text, max_length=60)
        return (
            f"WorkflowResult("
            f"source={self.source!r}, "
            f"latency={self.latency_ms:.0f}ms, "
            f"output={preview!r})"
        )


# ============================================================
# Workflow Orchestrator
# ============================================================


class Workflow:
    """
    Central orchestrator that coordinates Memory, Plugin, and Model Router.

    Usage:
        workflow = Workflow(memory, model_router, plugin_loader)
        result = workflow.process("Hello!", session_id="abc")
        print(result.output_text)
    """

    def __init__(
        self,
        memory: Memory,
        model_router: ModelRouter,
        plugin_loader: Optional[PluginLoader] = None,
        knowledge_base: Optional['ChromaDBKnowledgeBase'] = None,
        max_context_messages: int = 10,
        cache_ttl_knowledge: int = 600,  # 10 min for KB search
        cache_ttl_model: int = 3600,     # 1 hour for model responses
        cache_max_size: int = 200,
    ):
        self.memory = memory
        self.model_router = model_router
        self.plugin_loader = plugin_loader
        self.knowledge_base = knowledge_base
        self.max_context_messages = max_context_messages

        # Initialize caches
        self.kb_cache = SimpleTTLCache(
            max_size=cache_max_size,
            ttl_seconds=cache_ttl_knowledge,
        )

        # Stats tracking
        self.total_processed: int = 0
        self.total_llm_calls: int = 0
        self.total_plugin_calls: int = 0
        self.total_kb_lookups: int = 0
        self.total_cache_hits: int = 0

        kb_status = f"knowledge={knowledge_base.__class__.__name__}" if knowledge_base else "knowledge=None"
        logger.info(
            f"Workflow initialized: "
            f"memory={memory.db_path}, "
            f"model={model_router.model.model_name}, "
            f"plugins={len(plugin_loader.get_all()) if plugin_loader else 0}, "
            f"{kb_status}, "
            f"kb_cache_ttl={cache_ttl_knowledge}s, "
            f"model_cache_ttl={cache_ttl_model}s"
        )

    # ── Main Processing ──

    def process(
        self,
        user_input: str,
        session_id: str,
        max_context: Optional[int] = None,
    ) -> WorkflowResult:
        """
        Execute one full workflow cycle (synchronous).

        Flow:
          1. Save user message to Memory
          2. Load context from Memory
          3. Try to execute a matching Plugin
          4. If no plugin matched, call Model Router with context
          5. Save assistant response to Memory
          6. Return WorkflowResult

        Args:
            user_input: The user's message text
            session_id: Active session ID
            max_context: Override default max_context_messages

        Returns:
            WorkflowResult with response or plugin result
        """
        start_time = time.time()

        if not user_input or not user_input.strip():
            raise AssistantError("User input cannot be empty")

        max_ctx = max_context or self.max_context_messages
        self.total_processed += 1

        # Step 1: Save user message
        self.memory.add_message(session_id, "user", user_input)

        # Step 2: Load context
        context = self.memory.get_context(session_id, limit=max_ctx)
        logger.debug(f"Loaded {len(context)} context messages for session {session_id}")

        # Step 3: Check plugins
        if self.plugin_loader:
            plugin_result = self._try_plugin(user_input)
            if plugin_result is not None:
                elapsed = (time.time() - start_time) * 1000
                self.total_plugin_calls += 1

                # Save plugin output as assistant message
                if plugin_result.success:
                    self.memory.add_message(session_id, "assistant", plugin_result.output)

                return WorkflowResult(
                    input=user_input,
                    plugin_result=plugin_result,
                    context_used=len(context),
                    latency_ms=elapsed,
                    source="plugin",
                    session_id=session_id,
                )

        # Step 4: Call Model Router
        response = self._call_model(user_input, context)

        # Step 5: Save assistant response
        self.memory.add_message(session_id, "assistant", response.text)

        elapsed = (time.time() - start_time) * 1000
        self.total_llm_calls += 1

        return WorkflowResult(
            input=user_input,
            response=response,
            context_used=len(context),
            latency_ms=elapsed,
            source="llm",
            session_id=session_id,
        )

    async def process_async(
        self,
        user_input: str,
        session_id: str,
        max_context: Optional[int] = None,
    ) -> WorkflowResult:
        """
        Execute one full workflow cycle (asynchronous / non-blocking).

        Flow is identical to process() but uses async model calls:
          1. Save user message to Memory
          2. Load context from Memory
          3. Try to execute a matching Plugin
          4. If no plugin matched, call Model Router with context (async)
          5. Save assistant response to Memory
          6. Return WorkflowResult

        Args:
            user_input: The user's message text
            session_id: Active session ID
            max_context: Override default max_context_messages

        Returns:
            WorkflowResult with response or plugin result
        """
        start_time = time.time()

        if not user_input or not user_input.strip():
            raise AssistantError("User input cannot be empty")

        max_ctx = max_context or self.max_context_messages
        self.total_processed += 1

        # Step 1: Save user message
        self.memory.add_message(session_id, "user", user_input)

        # Step 2: Load context
        context = self.memory.get_context(session_id, limit=max_ctx)
        logger.debug(f"Loaded {len(context)} context messages for session {session_id}")

        # Step 3: Check plugins (sync — fast local operation)
        if self.plugin_loader:
            plugin_result = self._try_plugin(user_input)
            if plugin_result is not None:
                elapsed = (time.time() - start_time) * 1000
                self.total_plugin_calls += 1

                # Save plugin output as assistant message
                if plugin_result.success:
                    self.memory.add_message(session_id, "assistant", plugin_result.output)

                return WorkflowResult(
                    input=user_input,
                    plugin_result=plugin_result,
                    context_used=len(context),
                    latency_ms=elapsed,
                    source="plugin",
                    session_id=session_id,
                )

        # Step 4: Call Model Router (async — non-blocking API call!)
        response = await self._call_model_async(user_input, context)

        # Step 5: Save assistant response
        self.memory.add_message(session_id, "assistant", response.text)

        elapsed = (time.time() - start_time) * 1000
        self.total_llm_calls += 1

        return WorkflowResult(
            input=user_input,
            response=response,
            context_used=len(context),
            latency_ms=elapsed,
            source="llm",
            session_id=session_id,
        )

    # ── Plugin Resolution ──

    def _try_plugin(self, user_input: str) -> Optional[PluginResult]:
        """Check if any plugin can handle this input. Returns None if no match."""
        if not self.plugin_loader:
            return None

        plugins = self.plugin_loader.get_all()
        if not plugins:
            return None

        for plugin in plugins:
            try:
                # Execute plugin directly to see if it can handle the input
                result = plugin.execute(user_input)
                # Only use plugin result if it's successful
                if result.success:
                    logger.debug(f"Plugin '{plugin.name}' handled input: {user_input!r}")
                    return result
            except Exception as e:
                logger.debug(f"Plugin '{plugin.name}' cannot handle input: {e}")
                continue

        return None

    # ── Knowledge Base Lookup (with caching) ──

    def _enrich_with_knowledge(self, prompt: str) -> str:
        """Search knowledge base and append relevant context to the prompt.

        Results are cached using SimpleTTLCache to avoid repeated searches
        for similar queries within the TTL window.
        """
        if not self.knowledge_base or not self.knowledge_base.available:
            return prompt

        # Check cache first
        cache_key = make_knowledge_cache_key(prompt, n_results=3)
        cached = self.kb_cache.get(cache_key)
        if cached is not None:
            if cached == "__no_results__":
                return prompt  # No results, no enrichment needed
            self.total_cache_hits += 1
            logger.debug("Knowledge cache HIT")
            return cached

        # Cache miss — search knowledge base
        try:
            results = self.knowledge_base.search(prompt, n_results=3)
            if not results:
                # Cache the miss so we don't re-query for the same prompt
                self.kb_cache.set(cache_key, "__no_results__")
                return prompt

            self.total_kb_lookups += 1

            # Build knowledge context block
            knowledge_lines = []
            for r in results:
                preview = r.content.strip()[:300]
                knowledge_lines.append(
                    f"[From {r.filename}] (score: {r.score:.2f}): {preview}"
                )

            knowledge_block = "\n\n".join(knowledge_lines)
            enriched = (
                f"{prompt}\n\n"
                f"--- Relevant Knowledge ---\n"
                f"{knowledge_block}\n"
                f"---\n\n"
                f"Use the above knowledge to answer the user's question if relevant."
            )

            # Store in cache
            self.kb_cache.set(cache_key, enriched)

            logger.debug(f"Enriched prompt with {len(results)} knowledge chunks")
            return enriched

        except Exception as e:
            logger.warning(f"Knowledge enrichment failed: {e}")
            return prompt

    # ── Web Search Enrichment ──

    def _enrich_with_web_search(self, prompt: str) -> str:
        """Auto-detect questions and inject web search results into the prompt.

        If the prompt looks like a question (contains ? or starts with question words)
        and the web_search plugin is available, automatically search and inject results.
        """
        if not self.plugin_loader:
            return prompt

        web_search = self.plugin_loader.get("web_search")
        if web_search is None:
            return prompt

        # Only trigger for question-like prompts (not simple commands)
        prompt_lower = prompt.strip().lower()
        is_question = (
            "?" in prompt
            or prompt_lower.startswith(("what", "why", "how", "who", "where", "when", "which", "can", "is", "are", "do", "does", "has", "have", "tell", "explain", "define"))
            or any(w in prompt_lower for w in ["what is", "what are", "how to", "how do", "meaning of"])
        )

        # Skip very short prompts (commands, greetings)
        is_greeting = len(prompt.strip().split()) <= 3 and not is_question

        if not is_question or is_greeting:
            return prompt

        # Execute web search
        try:
            result = web_search.execute(prompt)
            if result.success and result.data:
                # Format as markdown block
                web_lines = ["### 🌐 Kết quả tìm kiếm web:\n"]
                for i, r in enumerate(result.data[:3], 1):
                    title = r.get("title", "")
                    snippet = r.get("snippet", "")[:200]
                    url = r.get("url", "")
                    web_lines.append(f"{i}. **{title}**")
                    if snippet:
                        web_lines.append(f"   > {snippet}")
                    if url:
                        web_lines.append(f"   🔗 {url}")
                    web_lines.append("")

                web_block = "\n".join(web_lines)
                enriched = (
                    f"{prompt}\n\n"
                    f"{web_block}"
                )
                logger.debug("Enriched prompt with web search results")
                return enriched

        except Exception as e:
            logger.debug(f"Web search enrichment failed: {e}")

        return prompt

    # ── Model Router Call ──

    def _call_model(self, prompt: str, context: list[dict]) -> ModelResponse:
        """Send prompt + context to the model router, enriched with knowledge and web search if available."""
        # Enrich with knowledge base first
        enriched = self._enrich_with_knowledge(prompt)
        # Then enrich with web search (if applicable)
        enriched = self._enrich_with_web_search(enriched)
        logger.debug(
            f"Calling model router with {len(context)} context messages"
            f"{" (enriched)" if enriched != prompt else ""}"
        )
        return self.model_router.generate(enriched, context=context)

    async def _call_model_async(self, prompt: str, context: list[dict]) -> ModelResponse:
        """Async version of _call_model — uses generate_async for non-blocking API calls."""
        # Enrich with knowledge base first
        enriched = self._enrich_with_knowledge(prompt)
        # Then enrich with web search (if applicable)
        enriched = self._enrich_with_web_search(enriched)
        logger.debug(
            f"Calling model router (async) with {len(context)} context messages"
            f"{" (enriched)" if enriched != prompt else ""}"
        )
        return await self.model_router.generate_async(enriched, context=context)

    # ── Reporting ──

    def get_stats(self) -> dict:
        """Get workflow execution statistics."""
        kb_cache_stats = self.kb_cache.get_stats() if hasattr(self, 'kb_cache') else {}
        return {
            "total_processed": self.total_processed,
            "total_llm_calls": self.total_llm_calls,
            "total_plugin_calls": self.total_plugin_calls,
            "total_kb_lookups": self.total_kb_lookups,
            "total_cache_hits": self.total_cache_hits,
            "context_limit": self.max_context_messages,
            "kb_cache": {
                "size": kb_cache_stats.get("size", 0),
                "max_size": kb_cache_stats.get("max_size", 0),
                "hit_rate_pct": kb_cache_stats.get("hit_rate_pct", 0),
            },
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"Workflow(processed={stats['total_processed']}, "
            f"llm={stats['total_llm_calls']}, "
            f"plugins={stats['total_plugin_calls']})"
        )
