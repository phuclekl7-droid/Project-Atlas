"""
Request Interceptor Hooks (Feature #9).
Pre/post processing hooks around model calls for safety checks, logging, and transformation.

Usage:
    chain = InterceptorChain()
    chain.add_pre_hook("pii_mask", lambda ctx: mask_pii(ctx["prompt"]))
    chain.add_post_hook("log", lambda ctx: logger.info(f"Response: {len(ctx['response'])} chars"))
    ctx = chain.run("Hello world!")
"""

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.core import setup_logger

logger = setup_logger("interceptor")


@dataclass
class HookContext:
    """Context passed through the interceptor chain."""

    prompt: str
    response: Optional[str] = None
    provider: str = ""
    model_name: str = ""
    session_id: str = ""
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    cancelled: bool = False
    cancel_reason: str = ""

    @property
    def aborted(self) -> bool:
        return self.cancelled


HookFn = Callable[[HookContext], HookContext]


@dataclass
class HookDef:
    """Definition of a single hook with metadata."""

    name: str
    fn: HookFn
    order: int = 100  # Lower runs first
    description: str = ""


class InterceptorChain:
    """
    Chain of pre/post hooks for model call processing.

    Pre-hooks run before the model call (input transformation/validation)
    Post-hooks run after the model call (output transformation/logging)

    Usage:
        chain = InterceptorChain()

        # Add hooks
        chain.add_pre_hook("validate", validate_fn, order=10)
        chain.add_post_hook("log", log_fn)

        # Run chain
        ctx = chain.run_pre("my prompt", provider="openai")
        if ctx.aborted:
            print(f"Cancelled: {ctx.cancel_reason}")
        else:
            response = call_model(ctx.prompt)
            ctx = chain.run_post(ctx, response)
    """

    def __init__(self):
        self._pre_hooks: list[HookDef] = []
        self._post_hooks: list[HookDef] = []
        self._stats: dict[str, int] = {"pre_run": 0, "post_run": 0, "cancelled": 0}

    def add_pre_hook(
        self,
        name: str,
        fn: HookFn,
        order: int = 100,
        description: str = "",
    ) -> "InterceptorChain":
        """Add a pre-model-call hook."""
        self._pre_hooks.append(HookDef(name=name, fn=fn, order=order, description=description))
        self._pre_hooks.sort(key=lambda h: h.order)
        return self

    def add_post_hook(
        self,
        name: str,
        fn: HookFn,
        order: int = 100,
        description: str = "",
    ) -> "InterceptorChain":
        """Add a post-model-call hook."""
        self._post_hooks.append(HookDef(name=name, fn=fn, order=order, description=description))
        self._post_hooks.sort(key=lambda h: h.order)
        return self

    def remove_hook(self, name: str) -> bool:
        """Remove a hook by name. Returns True if found."""
        before = len(self._pre_hooks) + len(self._post_hooks)
        self._pre_hooks = [h for h in self._pre_hooks if h.name != name]
        self._post_hooks = [h for h in self._post_hooks if h.name != name]
        return len(self._pre_hooks) + len(self._post_hooks) < before

    def run_pre(
        self,
        prompt: str,
        provider: str = "",
        model_name: str = "",
        session_id: str = "",
    ) -> HookContext:
        """Run all pre-hooks in order. Returns the final context."""
        ctx = HookContext(
            prompt=prompt,
            provider=provider,
            model_name=model_name,
            session_id=session_id,
        )
        self._stats["pre_run"] += 1
        for hook in self._pre_hooks:
            try:
                ctx = hook.fn(ctx)
                if ctx.aborted:
                    self._stats["cancelled"] += 1
                    logger.info(f"Request cancelled by pre-hook '{hook.name}': {ctx.cancel_reason}")
                    return ctx
            except Exception as e:
                logger.warning(f"Pre-hook '{hook.name}' raised error: {e}")
                ctx.cancelled = True
                ctx.cancel_reason = f"Hook '{hook.name}' error: {e}"
                self._stats["cancelled"] += 1
                return ctx
        return ctx

    def run_post(self, ctx: HookContext, response_text: str) -> HookContext:
        """Run all post-hooks. Returns the final context (may modify response)."""
        if ctx.aborted:
            return ctx
        ctx.response = response_text
        self._stats["post_run"] += 1
        for hook in self._post_hooks:
            try:
                ctx = hook.fn(ctx)
            except Exception as e:
                logger.warning(f"Post-hook '{hook.name}' raised error: {e}")
        return ctx

    def clear(self) -> None:
        """Remove all hooks."""
        self._pre_hooks.clear()
        self._post_hooks.clear()

    def list_hooks(self) -> dict[str, list[dict]]:
        """List all registered hooks."""
        return {
            "pre": [{"name": h.name, "order": h.order, "description": h.description} for h in self._pre_hooks],
            "post": [{"name": h.name, "order": h.order, "description": h.description} for h in self._post_hooks],
        }

    def get_stats(self) -> dict:
        """Get hook execution statistics."""
        return {**self._stats, "pre_count": len(self._pre_hooks), "post_count": len(self._post_hooks)}


# ============================================================
# Built-in Hook Factories
# ============================================================


def make_length_limit_hook(max_chars: int = 10000) -> HookFn:
    """Create a hook that rejects prompts exceeding max_chars."""
    def _hook(ctx: HookContext) -> HookContext:
        if len(ctx.prompt) > max_chars:
            ctx.cancelled = True
            ctx.cancel_reason = f"Prompt exceeds {max_chars} char limit ({len(ctx.prompt)} chars)"
        return ctx
    return _hook


def make_logging_hook() -> HookFn:
    """Create a hook that logs request/response info."""
    def _hook(ctx: HookContext) -> HookContext:
        if ctx.response is not None:
            logger.info(
                f"[Interceptor] {ctx.provider}: "
                f"prompt={len(ctx.prompt)}chars, "
                f"response={len(ctx.response)}chars, "
                f"latency={ctx.latency_ms:.0f}ms"
            )
        else:
            logger.info(f"[Interceptor] Pre-call: {ctx.provider}, prompt={len(ctx.prompt)}chars")
        return ctx
    return _hook


def make_response_length_limit_hook(max_chars: int = 50000) -> HookFn:
    """Create a hook that truncates overly long responses."""
    def _hook(ctx: HookContext) -> HookContext:
        if ctx.response and len(ctx.response) > max_chars:
            ctx.response = ctx.response[:max_chars] + "\n\n...[truncated by interceptor hook]"
        return ctx
    return _hook
