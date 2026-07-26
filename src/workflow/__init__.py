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
    ):
        self.memory = memory
        self.model_router = model_router
        self.plugin_loader = plugin_loader
        self.knowledge_base = knowledge_base
        self.max_context_messages = max_context_messages

        # Stats tracking
        self.total_processed: int = 0
        self.total_llm_calls: int = 0
        self.total_plugin_calls: int = 0
        self.total_kb_lookups: int = 0

        kb_status = f"knowledge={knowledge_base.__class__.__name__}" if knowledge_base else "knowledge=None"
        logger.info(
            f"Workflow initialized: "
            f"memory={memory.db_path}, "
            f"model={model_router.model.model_name}, "
            f"plugins={len(plugin_loader.get_all()) if plugin_loader else 0}, "
            f"{kb_status}"
        )

    # ── Main Processing ──

    def process(
        self,
        user_input: str,
        session_id: str,
        max_context: Optional[int] = None,
    ) -> WorkflowResult:
        """
        Execute one full workflow cycle.

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

    # ── Knowledge Base Lookup ──

    def _enrich_with_knowledge(self, prompt: str) -> str:
        """Search knowledge base and append relevant context to the prompt."""
        if not self.knowledge_base or not self.knowledge_base.available:
            return prompt

        try:
            results = self.knowledge_base.search(prompt, n_results=3)
            if not results:
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

            logger.debug(f"Enriched prompt with {len(results)} knowledge chunks")
            return enriched

        except Exception as e:
            logger.warning(f"Knowledge enrichment failed: {e}")
            return prompt

    # ── Model Router Call ──

    def _call_model(self, prompt: str, context: list[dict]) -> ModelResponse:
        """Send prompt + context to the model router, enriched with knowledge if available."""
        enriched_prompt = self._enrich_with_knowledge(prompt)
        logger.debug(
            f"Calling model router with {len(context)} context messages"
            f"{" (enriched with knowledge)" if enriched_prompt != prompt else ""}"
        )
        return self.model_router.generate(enriched_prompt, context=context)

    # ── Reporting ──

    def get_stats(self) -> dict:
        """Get workflow execution statistics."""
        return {
            "total_processed": self.total_processed,
            "total_llm_calls": self.total_llm_calls,
            "total_plugin_calls": self.total_plugin_calls,
            "total_kb_lookups": self.total_kb_lookups,
            "context_limit": self.max_context_messages,
        }

    def __repr__(self) -> str:
        stats = self.get_stats()
        return (
            f"Workflow(processed={stats['total_processed']}, "
            f"llm={stats['total_llm_calls']}, "
            f"plugins={stats['total_plugin_calls']})"
        )
