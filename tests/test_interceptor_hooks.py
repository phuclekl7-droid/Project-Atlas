"""
Tests for Feature #9: Request Interceptor Hooks.
"""

import pytest

from src.core.interceptor_hooks import (
    InterceptorChain,
    HookContext,
    make_length_limit_hook,
    make_logging_hook,
    make_response_length_limit_hook,
)


class TestHookContext:
    """Tests for the HookContext dataclass."""

    def test_default_context(self):
        ctx = HookContext(prompt="Hello")
        assert ctx.prompt == "Hello"
        assert ctx.response is None
        assert not ctx.aborted
        assert ctx.cancel_reason == ""

    def test_aborted_property(self):
        ctx = HookContext(prompt="test", cancelled=True)
        assert ctx.aborted


class TestInterceptorChain:
    """Tests for the InterceptorChain class."""

    def test_add_and_run_pre_hook(self):
        chain = InterceptorChain()

        def uppercase_prompt(ctx: HookContext) -> HookContext:
            ctx.prompt = ctx.prompt.upper()
            return ctx

        chain.add_pre_hook("uppercase", uppercase_prompt)
        ctx = chain.run_pre("hello")
        assert ctx.prompt == "HELLO"

    def test_add_and_run_post_hook(self):
        chain = InterceptorChain()

        def add_tags(ctx: HookContext) -> HookContext:
            ctx.response = ctx.response + " [END]"
            return ctx

        chain.add_post_hook("add_tags", add_tags)
        ctx = HookContext(prompt="test")
        ctx = chain.run_post(ctx, "response text")
        assert ctx.response == "response text [END]"

    def test_pre_hook_cancels_request(self):
        chain = InterceptorChain()

        def cancel_if_hello(ctx: HookContext) -> HookContext:
            if "hello" in ctx.prompt.lower():
                ctx.cancelled = True
                ctx.cancel_reason = "No hello allowed"
            return ctx

        chain.add_pre_hook("no_hello", cancel_if_hello)
        ctx = chain.run_pre("hello world")
        assert ctx.aborted
        assert "No hello allowed" in ctx.cancel_reason

    def test_pre_hook_does_not_cancel(self):
        chain = InterceptorChain()

        def cancel_if_hello(ctx: HookContext) -> HookContext:
            if "hello" in ctx.prompt.lower():
                ctx.cancelled = True
                ctx.cancel_reason = "No hello allowed"
            return ctx

        chain.add_pre_hook("no_hello", cancel_if_hello)
        ctx = chain.run_pre("goodbye")
        assert not ctx.aborted

    def test_hook_order(self):
        chain = InterceptorChain()

        results = []

        def make_hook(name):
            def hook(ctx):
                results.append(name)
                return ctx
            return hook

        chain.add_pre_hook("first", make_hook("first"), order=10)
        chain.add_pre_hook("second", make_hook("second"), order=20)
        chain.add_pre_hook("third", make_hook("third"), order=30)

        chain.run_pre("test")
        assert results == ["first", "second", "third"]

    def test_remove_hook(self):
        chain = InterceptorChain()
        chain.add_pre_hook("test_hook", lambda ctx: ctx)
        assert len(chain.list_hooks()["pre"]) == 1
        assert chain.remove_hook("test_hook")
        assert len(chain.list_hooks()["pre"]) == 0

    def test_remove_nonexistent_hook(self):
        chain = InterceptorChain()
        assert not chain.remove_hook("nonexistent")

    def test_clear_all_hooks(self):
        chain = InterceptorChain()
        chain.add_pre_hook("a", lambda ctx: ctx)
        chain.add_post_hook("b", lambda ctx: ctx)
        chain.clear()
        assert len(chain.list_hooks()["pre"]) == 0
        assert len(chain.list_hooks()["post"]) == 0

    def test_run_post_on_cancelled_context(self):
        chain = InterceptorChain()
        ctx = HookContext(prompt="test", cancelled=True)
        ctx = chain.run_post(ctx, "response")
        assert ctx.response is None  # Not set because cancelled

    def test_pre_hook_error_handling(self):
        chain = InterceptorChain()

        def broken_hook(ctx):
            raise ValueError("Something broke")

        chain.add_pre_hook("broken", broken_hook)
        ctx = chain.run_pre("test")
        assert ctx.aborted
        assert "broken" in ctx.cancel_reason

    def test_get_stats(self):
        chain = InterceptorChain()
        chain.add_pre_hook("a", lambda ctx: ctx)
        chain.add_post_hook("b", lambda ctx: ctx)
        stats = chain.get_stats()
        assert stats["pre_count"] == 1
        assert stats["post_count"] == 1
        assert stats["pre_run"] == 0
        assert stats["post_run"] == 0

        chain.run_pre("test")
        stats = chain.get_stats()
        assert stats["pre_run"] == 1

    def test_list_hooks(self):
        chain = InterceptorChain()
        chain.add_pre_hook("hook1", lambda ctx: ctx, order=50, description="Test hook")
        hooks = chain.list_hooks()
        assert len(hooks["pre"]) == 1
        assert hooks["pre"][0]["name"] == "hook1"
        assert hooks["pre"][0]["order"] == 50


class TestBuiltinHooks:
    """Tests for built-in hook factories."""

    def test_length_limit_hook_allows_short(self):
        hook = make_length_limit_hook(max_chars=100)
        ctx = hook(HookContext(prompt="short text"))
        assert not ctx.aborted

    def test_length_limit_hook_blocks_long(self):
        hook = make_length_limit_hook(max_chars=10)
        ctx = hook(HookContext(prompt="this is too long for the limit"))
        assert ctx.aborted
        assert "exceeds" in ctx.cancel_reason

    def test_logging_hook_pre(self):
        hook = make_logging_hook()
        ctx = hook(HookContext(prompt="test", provider="mock"))
        assert not ctx.aborted
        assert ctx.prompt == "test"

    def test_logging_hook_post(self):
        hook = make_logging_hook()
        ctx = HookContext(prompt="test", provider="mock", latency_ms=150.0)
        ctx.response = "response text"
        ctx = hook(ctx)
        assert ctx.response == "response text"

    def test_response_length_limit_hook(self):
        hook = make_response_length_limit_hook(max_chars=20)
        ctx = HookContext(prompt="test")
        ctx.response = "A" * 100
        ctx = hook(ctx)
        assert len(ctx.response) < 100
        assert "truncated" in ctx.response

    def test_response_length_limit_hook_short_response(self):
        hook = make_response_length_limit_hook(max_chars=100)
        ctx = HookContext(prompt="test")
        ctx.response = "short"
        ctx = hook(ctx)
        assert ctx.response == "short"
