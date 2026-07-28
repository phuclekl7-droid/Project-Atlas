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
from typing import AsyncIterator, Optional

from src.core import (
    AssistantError,
    ConfigurationError,
    ModelConnectionError,
    PluginExecutionError,
    setup_logger,
    truncate_text,
)
from src.core.cache import SimpleTTLCache, make_knowledge_cache_key
from src.core.token_counter import TokenCounter
from src.memory import Memory
from src.model_router import ModelResponse, ModelRouter
from src.model_router.smart_router import SmartRouter
from src.plugin import PluginLoader, PluginResult
from src.anonymizer import mask_pii, should_mask
from src.core.content_filter import ContentFilter

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

        # Token counter for context management
        self._token_counter = TokenCounter()

        # Smart Router for multi-model conversations
        self._smart_router = SmartRouter(model_router.settings)
        self.multi_model_enabled = getattr(model_router.settings, 'multi_model_enabled', False)

        # Self-Correction Agent (Feature 62) — disabled by default to avoid double cost
        self._self_correction_enabled = False

        # Content Moderation Filter (Feature 78)
        self._content_filter = ContentFilter()
        self.content_filter_enabled = True  # Can be toggled off for power users

        # Forget Memory command tracking
        self._last_forget_request: Optional[str] = None

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
        **model_kwargs,
    ) -> WorkflowResult:
        """
        Execute one full workflow cycle (synchronous).

        Flow:
          0a. Check /forget command
          0b. Content moderation filter
          1. Save user message to Memory
          2. Load context from Memory
          3. Try to execute a matching Plugin
          4. If no plugin matched, call Model Router with context (with PII masking)
          5. Self-Correction (if enabled)
          6. Save assistant response to Memory
          7. Return WorkflowResult

        Args:
            user_input: The user's message text
            session_id: Active session ID
            max_context: Override default max_context_messages
            **model_kwargs: Additional kwargs passed to the model (temperature, top_p, etc.)

        Returns:
            WorkflowResult with response or plugin result
        """
        start_time = time.time()

        if not user_input or not user_input.strip():
            raise AssistantError("User input cannot be empty")

        max_ctx = max_context or self.max_context_messages
        self.total_processed += 1

        # Step 0a: Check for /forget command (Feature 19)
        if user_input.strip().lower().startswith("/forget"):
            return self._handle_forget_command(user_input, session_id)

        # Step 0b: Content Moderation Filter (Feature 78)
        if self.content_filter_enabled:
            mod_result = self._content_filter.check_input(user_input)
            if mod_result.action == "block":
                elapsed = (time.time() - start_time) * 1000
                warning_msg = (
                    f"⚠️ **Nội dung bị chặn**\n\n"
                    f"Tin nhắn của bạn đã bị lọc tự động do chứa "
                    f"nội dung không phù hợp: "
                    f"**{', '.join(mod_result.categories)}**.\n\n"
                    f"Vui lòng đặt lại câu hỏi theo cách khác."
                )
                self.memory.add_message(session_id, "user", user_input)
                self.memory.add_message(session_id, "assistant", warning_msg)
                return WorkflowResult(
                    input=user_input,
                    response=ModelResponse(
                        text=warning_msg, model_name="filter", provider="system"
                    ),
                    context_used=0,
                    latency_ms=elapsed,
                    source="filter",
                    session_id=session_id,
                )
            elif mod_result.action == "warn":
                logger.debug(f"Content filter warning: {mod_result.categories}")

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

        # Step 4: PII Anonymization (Feature 71)
        provider_for_pii = self.model_router.settings.model_provider
        if should_mask(provider_for_pii):
            user_input_masked = mask_pii(user_input)
            logger.debug(f"Applied PII masking for provider {provider_for_pii}")
        else:
            user_input_masked = user_input

        # Step 5: Call Model Router (with Smart Routing if enabled)
        response = self._call_model_with_routing(user_input_masked, context, **model_kwargs)

        # Step 6: Self-Correction (Feature 62 — opt-in via session flag)
        if self._self_correction_enabled and len(response.text) > 20:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                corrected = loop.run_until_complete(self._self_correct(response.text, user_input))
                if corrected != response.text:
                    response.text = corrected
                    logger.debug("Self-correction applied (sync)")
            except Exception as e:
                logger.debug(f"Self-correction skipped (sync): {e}")

        # Step 5: Save assistant response with provider info
        self.memory.add_message(
            session_id, "assistant", response.text,
            provider=response.provider,
        )

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
        **model_kwargs,
    ) -> WorkflowResult:
        """
        Execute one full workflow cycle (asynchronous / non-blocking).

        Flow is identical to process() but uses async model calls:
          0a. Check /forget command
          0b. Content moderation filter
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
            **model_kwargs: Additional kwargs passed to the model (temperature, top_p, etc.)

        Returns:
            WorkflowResult with response or plugin result
        """
        start_time = time.time()

        if not user_input or not user_input.strip():
            raise AssistantError("User input cannot be empty")

        max_ctx = max_context or self.max_context_messages
        self.total_processed += 1

        # Step 0a: Check for /forget command (Feature 19)
        if user_input.strip().lower().startswith("/forget"):
            return self._handle_forget_command(user_input, session_id)

        # Step 0b: Content Moderation Filter (Feature 78)
        if self.content_filter_enabled:
            mod_result = self._content_filter.check_input(user_input)
            if mod_result.action == "block":
                elapsed = (time.time() - start_time) * 1000
                warning_msg = (
                    f"⚠️ **Nội dung bị chặn**\n\n"
                    f"Tin nhắn của bạn đã bị lọc tự động do chứa "
                    f"nội dung không phù hợp: "
                    f"**{', '.join(mod_result.categories)}**.\n\n"
                    f"Vui lòng đặt lại câu hỏi theo cách khác."
                )
                self.memory.add_message(session_id, "user", user_input)
                self.memory.add_message(session_id, "assistant", warning_msg)
                return WorkflowResult(
                    input=user_input,
                    response=ModelResponse(
                        text=warning_msg, model_name="filter", provider="system"
                    ),
                    context_used=0,
                    latency_ms=elapsed,
                    source="filter",
                    session_id=session_id,
                )
            elif mod_result.action == "warn":
                logger.debug(f"Content filter warning: {mod_result.categories}")

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

        # Step 4: Call Model Router with Smart Routing if enabled (async)
        response = await self._call_model_with_routing_async(user_input, context, **model_kwargs)

        # Step 5: Save assistant response with provider info
        self.memory.add_message(
            session_id, "assistant", response.text,
            provider=response.provider,
        )

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

    def _call_model_with_routing(self, prompt: str, context: list[dict], **model_kwargs) -> ModelResponse:
        """
        Call model router with Smart Routing (sync).

        If multi_model_enabled is True, uses SmartRouter to select the
        best provider for this prompt. Otherwise uses default provider.

        Args:
            prompt: The enriched prompt text
            context: Conversation history
            **model_kwargs: Additional kwargs (temperature, top_p, etc.)

        Returns:
            ModelResponse with provider info
        """
        enriched = self._enrich_with_knowledge(prompt)
        enriched = self._enrich_with_web_search(enriched)

        if self.multi_model_enabled:
            provider_name, reason = self._smart_router.route_with_reason(prompt)
            logger.debug(f"SmartRouter: routing to {provider_name} ({reason})")
            response = self.model_router.generate_with_provider(
                provider_name, enriched, context=context, **model_kwargs
            )
        else:
            logger.debug(f"Using default provider: {self.model_router.settings.model_provider}")
            response = self.model_router.generate(enriched, context=context, **model_kwargs)

        return response

    async def _call_model_with_routing_async(self, prompt: str, context: list[dict], **model_kwargs) -> ModelResponse:
        """
        Call model router with Smart Routing (async).

        If multi_model_enabled is True, uses SmartRouter to select the
        best provider for this prompt. Otherwise uses default provider.

        Args:
            prompt: The enriched prompt text
            context: Conversation history
            **model_kwargs: Additional kwargs (temperature, top_p, etc.)

        Returns:
            ModelResponse with provider info
        """
        enriched = self._enrich_with_knowledge(prompt)
        enriched = self._enrich_with_web_search(enriched)

        if self.multi_model_enabled:
            provider_name, reason = self._smart_router.route_with_reason(prompt)
            logger.debug(f"SmartRouter: routing async to {provider_name} ({reason})")
            response = await self.model_router.generate_with_provider_async(
                provider_name, enriched, context=context, **model_kwargs
            )
        else:
            logger.debug(f"Using default provider (async): {self.model_router.settings.model_provider}")
            response = await self.model_router.generate_async(enriched, context=context, **model_kwargs)

        return response

    # ── Streaming ──

    async def process_stream(
        self,
        user_input: str,
        session_id: str,
        max_context: Optional[int] = None,
        **model_kwargs,
    ) -> AsyncIterator[str]:
        """
        Execute workflow cycle with streaming response.

        Same flow as process() but yields tokens one by one as they arrive
        from the model. Plugin results are yielded as a single token.

        Args:
            user_input: The user's message text
            session_id: Active session ID
            max_context: Override default max_context_messages
            **model_kwargs: Additional kwargs passed to the model (temperature, top_p, etc.)

        Yields:
            str: Response tokens (streamed live from the model)

        Usage:
            async for token in workflow.process_stream("Hello!", session_id="abc"):
                print(token, end="", flush=True)
        """
        if not user_input or not user_input.strip():
            raise AssistantError("User input cannot be empty")

        max_ctx = max_context or self.max_context_messages
        self.total_processed += 1

        # Step 0a: Check for /forget command (Feature 19)
        if user_input.strip().lower().startswith("/forget"):
            result = self._handle_forget_command(user_input, session_id)
            yield result.output_text
            return

        # Step 1: Save user message
        self.memory.add_message(session_id, "user", user_input)

        # Step 2: Load context
        context = self.memory.get_context(session_id, limit=max_ctx)
        logger.debug(f"Loaded {len(context)} context messages for session {session_id}")

        # Step 3: Check plugins (sync — fast local operation)
        if self.plugin_loader:
            plugin_result = self._try_plugin(user_input)
            if plugin_result is not None:
                self.total_plugin_calls += 1
                if plugin_result.success:
                    self.memory.add_message(session_id, "assistant", plugin_result.output)
                yield plugin_result.output
                return

        # Step 4: Stream from Model Router
        enriched = self._enrich_with_knowledge(user_input)
        enriched = self._enrich_with_web_search(enriched)

        if self.multi_model_enabled:
            provider_name, _ = self._smart_router.route_with_reason(user_input)
        else:
            provider_name = self.model_router.settings.model_provider

        # For streaming, use the default provider's stream (streaming + multi-model is complex)
        # Use generate_with_provider sync for the provider, then stream the cached response
        # Or just use default provider streaming
        full_response = []
        async for token in self.model_router.generate_stream(enriched, context=context, **model_kwargs):
            full_response.append(token)
            yield token

        # Step 5: Save full response to memory with provider info
        final_text = "".join(full_response)
        self.memory.add_message(session_id, "assistant", final_text, provider=provider_name)

        self.total_llm_calls += 1

    # ── Session Summarization ──

    async def summarize_session(
        self,
        session_id: str,
        max_messages: int = 50,
    ) -> Optional[str]:
        """
        Auto-summarize a long conversation to save context window space.

        Fetches recent messages from the session and asks the LLM to
        generate a concise summary. The summary is saved as a system message
        at the beginning of the session context.

        Returns the summary text if successful, None otherwise.

        Args:
            session_id: The session to summarize
            max_messages: Max messages to include in summarization

        Returns:
            Summary string, or None if session is too short to summarize
        """
        messages = self.memory.get_messages(session_id, limit=max_messages)

        # Only summarize if there are enough messages
        if len(messages) < 6:
            logger.debug(f"Session {session_id}: too short ({len(messages)} msgs) to summarize")
            return None

        # Build the conversation text to summarize
        lines = []
        for m in messages:
            role_label = "User" if m.role == "user" else "Assistant"
            content = m.text_content if hasattr(m, 'text_content') else m.content
            # Truncate very long messages
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"{role_label}: {content}")

        conversation_text = "\n".join(lines)

        # Calculate token estimate
        estimated_tokens = self._token_counter.count_tokens(conversation_text)
        if estimated_tokens > 12000:
            # Too long — use only last 30 messages
            messages = messages[-30:]
            lines = []
            for m in messages:
                role_label = "User" if m.role == "user" else "Assistant"
                content = m.text_content if hasattr(m, 'text_content') else m.content
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(f"{role_label}: {content}")
            conversation_text = "\n".join(lines)

        summarize_prompt = (
            f"Hãy tóm tắt ngắn gọn cuộc trò chuyện sau đây bằng tiếng Việt. "
            f"Nêu rõ chủ đề chính, các câu hỏi quan trọng, và kết luận (nếu có).\n\n"
            f"--- Cuộc trò chuyện ---\n{conversation_text}\n"
            f"---\n\nTóm tắt:"
        )

        try:
            # Use mock model for summarization with default provider
            response = await self.model_router.generate_async(
                summarize_prompt, use_cache=True
            )
            summary = response.text.strip()

            if len(summary) < 10:
                logger.warning(f"Session {session_id}: summary too short ({len(summary)} chars)")
                return None

            # Save summary as a system message (at the beginning of context)
            summary_msg = f"[📋 Tóm tắt hội thoại] {summary}"

            # Get existing summaries and replace or append
            existing_msgs = self.memory.get_messages(session_id, limit=5)
            summary_exists = False
            for m in existing_msgs:
                if m.role == "system" and "📋 Tóm tắt hội thoại" in m.content:
                    # Update existing summary
                    self.memory.update_message(session_id, m.id, summary_msg)
                    summary_exists = True
                    break

            if not summary_exists:
                # Get the first user message ID to insert before it
                # We'll just add a system message (it goes to the end, but context building handles ordering)
                self.memory.add_message(session_id, "system", summary_msg)

            logger.info(f"Session {session_id}: auto-summarized {len(messages)} msgs")
            return summary

        except Exception as e:
            logger.warning(f"Session summarization failed: {e}")
            return None

    # ── Forget Command Handler (Feature 19) ──

    def _handle_forget_command(self, user_input: str, session_id: str) -> WorkflowResult:
        """Handle the /forget command to delete messages by pattern."""
        start_time = time.time()

        # Parse the pattern: /forget <pattern>
        parts = user_input.strip().split(maxsplit=1)
        if len(parts) < 2:
            return WorkflowResult(
                input=user_input,
                response=ModelResponse(
                    text="Sử dụng: `/forget <từ_khóa>` để xóa các tin nhắn có chứa từ khóa đó.",
                    model_name="system",
                    provider="system",
                ),
                source="system",
                latency_ms=0,
                session_id=session_id,
            )

        pattern = parts[1].strip()
        if not pattern:
            return WorkflowResult(
                input=user_input,
                response=ModelResponse(
                    text="Vui lòng nhập từ khóa cần xóa. Ví dụ: `/forget tên tôi là...`",
                    model_name="system",
                    provider="system",
                ),
                source="system",
                latency_ms=0,
                session_id=session_id,
            )

        deleted = self.memory.forget_messages_by_pattern(session_id, pattern)
        elapsed = (time.time() - start_time) * 1000

        if deleted > 0:
            msg = f"🗑️ Đã xóa **{deleted}** tin nhắn có chứa từ khóa `{pattern}`."
        else:
            msg = f"🔍 Không tìm thấy tin nhắn nào chứa `{pattern}` trong session này."

        return WorkflowResult(
            input=user_input,
            response=ModelResponse(text=msg, model_name="system", provider="system"),
            source="system",
            latency_ms=elapsed,
            session_id=session_id,
        )

    # ── Self-Correction Agent (Feature 62) ──

    async def _self_correct(self, response_text: str, original_prompt: str) -> str:
        """
        Self-Correction Agent: Second-pass verification of model responses.

        After the initial LLM response, sends it back to the model for
        review. If the model identifies issues (inaccuracies, missing info,
        formatting problems), it generates an improved version.

        Args:
            response_text: The initial LLM response to verify
            original_prompt: The original user prompt (for context)

        Returns:
            The corrected response (or original if no correction needed)
        """
        if not response_text or len(response_text.strip()) < 20:
            # Skip correction for very short responses
            return response_text

        correction_prompt = (
            f"Bạn là một AI kiểm tra chất lượng (Quality Checker). "
            f"Hãy đọc câu hỏi gốc và câu trả lời dưới đây. "
            f"Nếu câu trả lời có vấn đề (sai sự thật, thiếu thông tin quan trọng, "
            f"định dạng lỗi, hoặc không trả lời đúng câu hỏi), hãy viết lại "
            f"câu trả lời đã được cải thiện. "
            f"Nếu câu trả lời đã tốt, chỉ cần trả lời: 'OK'\n\n"
            f"--- Câu hỏi gốc ---\n{original_prompt}\n\n"
            f"--- Câu trả lời cần kiểm tra ---\n{response_text}\n\n"
            f"---\nKết quả kiểm tra:"
        )

        try:
            correction = await self.model_router.generate_async(
                correction_prompt, use_cache=False
            )
            corrected = correction.text.strip()

            # If the model says 'OK', return original
            if corrected.upper().startswith("OK") or len(corrected) < 5:
                logger.debug("Self-correction: no changes needed")
                return response_text

            # Only use correction if it's significantly different from original
            if len(corrected) > len(response_text) * 0.5:
                logger.info("Self-correction: response was improved")
                return corrected

            return response_text

        except Exception as e:
            logger.warning(f"Self-correction failed: {e}")
            return response_text

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
