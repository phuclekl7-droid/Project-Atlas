"""
Automatic Prompt Optimization & Self-Correction Feedback Loop (Feature #107)

Provides a middleware layer that automatically:
1. Refines vague/ambiguous prompts before sending to the LLM
2. Validates LLM responses against expected schemas
3. Automatically retries with corrective feedback if the response is invalid
4. Maintains a history of optimizations for continuous improvement

Usage:
    optimizer = PromptOptimizer(model_router)
    result = optimizer.process("fix this code", context=history)
    # → Refined prompt → LLM → validation → (correct or retry) → result
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("core.prompt_optimizer")


@dataclass
class OptimizationResult:
    """Result of a prompt optimization cycle.

    Attributes:
        original_prompt: The user's original input
        refined_prompt: The optimized prompt sent to LLM
        response_text: The LLM's response
        valid: Whether the response passed validation
        retry_count: Number of retry attempts made
        total_latency_ms: Total time including retries
        corrections: List of correction messages used in retries
    """

    original_prompt: str
    refined_prompt: str = ""
    response_text: str = ""
    valid: bool = True
    retry_count: int = 0
    total_latency_ms: float = 0.0
    corrections: list[str] = field(default_factory=list)
    validation_error: str = ""


@dataclass
class OptimizerConfig:
    """Configuration for the prompt optimizer.

    Attributes:
        max_retries: Maximum number of self-correction retries
        enable_refinement: Whether to auto-refine prompts
        refinement_threshold: Minimum prompt length to trigger refinement
        validation_schema: Optional dict schema for response validation
        require_json: If True, validates response is valid JSON
        require_markdown: If True, checks for markdown formatting
        keywords_required: List of keywords that must appear in response
        custom_validator: Optional custom validation function
        refinement_prompt_template: Custom refinement prompt template
    """

    max_retries: int = 3
    enable_refinement: bool = True
    refinement_threshold: int = 15  # Minimum chars to consider for refinement
    require_json: bool = False
    require_markdown: bool = False
    keywords_required: list[str] = field(default_factory=list)
    custom_validator: Optional[Callable[[str], tuple[bool, str]]] = None
    refinement_prompt_template: str = ""

    # Built-in refinement prompts
    _DEFAULT_REFINEMENT_TEMPLATE = (
        "You are a prompt engineering assistant. Your task is to refine the user's "
        "input into a clear, specific, and well-structured prompt for an AI assistant.\n\n"
        "Original input: \"{prompt}\"\n\n"
        "Context: {context_summary}\n\n"
        "Please produce ONLY the refined prompt, with:\n"
        "1. Clear task description\n"
        "2. Specific format requirements\n"
        "3. Any constraints or preferences implied by the original\n"
        "Do NOT add explanations or meta-commentary."
    )

    _CORRECTION_TEMPLATE = (
        "Your previous response had an issue: {error}\n\n"
        "Please provide a corrected version. Make sure to:\n"
        "- Address the specific error mentioned above\n"
        "- Follow all original instructions\n"
        "- {additional_guidance}\n\n"
        "Original request: {original_prompt}"
    )


class PromptOptimizer:
    """Middleware that refines prompts and validates LLM responses with self-correction.

    Usage:
        optimizer = PromptOptimizer(model_router, config=OptimizerConfig(max_retries=2))

        # Simple usage
        result = optimizer.process("explain Python")
        print(result.response_text)

        # With context and custom validation
        result = optimizer.process(
            "generate a config",
            context=[{"role": "user", "content": "..."}],
            require_json=True,
        )
        if result.valid:
            config = json.loads(result.response_text)
    """

    def __init__(
        self,
        model_router: Any,
        config: Optional[OptimizerConfig] = None,
    ):
        """
        Args:
            model_router: A ModelRouter instance with a .generate() method
            config: Configuration for optimization behavior
        """
        self.router = model_router
        self.config = config or OptimizerConfig()
        self._optimization_history: list[OptimizationResult] = []
        self._refinement_cache: dict[str, str] = {}

    def process(
        self,
        prompt: str,
        context: Optional[list[dict]] = None,
        require_json: bool = False,
        require_markdown: bool = False,
        keywords_required: Optional[list[str]] = None,
        custom_validator: Optional[Callable[[str], tuple[bool, str]]] = None,
        **kwargs,
    ) -> OptimizationResult:
        """Process a prompt through the optimization pipeline.

        Args:
            prompt: The user's original input
            context: Optional conversation context
            require_json: If True, validate response is valid JSON
            require_markdown: If True, check for markdown formatting
            keywords_required: Keywords that must appear in response
            custom_validator: Custom validation function (response → (is_valid, error_msg))
            **kwargs: Additional args passed to model_router.generate()

        Returns:
            OptimizationResult with refined prompt, response, and validation status
        """
        start_time = time.time()
        context = context or []
        result = OptimizationResult(original_prompt=prompt)

        # ── Step 1: Refine the prompt ──
        use_refinement = (
            self.config.enable_refinement
            and len(prompt) >= self.config.refinement_threshold
        )

        if use_refinement:
            refined = self._refine_prompt(prompt, context)
            result.refined_prompt = refined
        else:
            result.refined_prompt = prompt

        # ── Step 2: Prepare validation config ──
        merged_require_json = require_json or self.config.require_json
        merged_require_md = require_markdown or self.config.require_markdown
        merged_keywords = keywords_required or self.config.keywords_required
        merged_validator = custom_validator or self.config.custom_validator

        # ── Step 3: Generate with self-correction loop ──
        final_prompt = result.refined_prompt
        attempts = 0

        while attempts <= self.config.max_retries:
            try:
                response = self.router.generate(final_prompt, context=context, **kwargs)
                response_text = response.text if hasattr(response, "text") else str(response)
                result.response_text = response_text
            except Exception as e:
                response_text = ""
                result.response_text = f"Error: {e}"
                result.valid = False
                result.validation_error = str(e)
                break

            # ── Validate the response ──
            is_valid, error_msg = self._validate_response(
                response_text,
                require_json=merged_require_json,
                require_markdown=merged_require_md,
                keywords=merged_keywords,
                custom_validator=merged_validator,
            )

            if is_valid:
                result.valid = True
                break
            else:
                attempts += 1
                result.retry_count = attempts
                result.validation_error = error_msg

                if attempts <= self.config.max_retries:
                    correction_prompt = self._build_correction_prompt(
                        error_msg, result.refined_prompt, attempts
                    )
                    result.corrections.append(correction_prompt)
                    final_prompt = correction_prompt
                else:
                    result.valid = False

        result.total_latency_ms = (time.time() - start_time) * 1000
        self._optimization_history.append(result)

        # Trim history to last 100 entries
        if len(self._optimization_history) > 100:
            self._optimization_history = self._optimization_history[-100:]

        return result

    def _refine_prompt(self, prompt: str, context: list[dict]) -> str:
        """Refine a user prompt into a clearer, more specific version.

        Args:
            prompt: Original user input
            context: Conversation context

        Returns:
            Refined prompt string
        """
        # Check cache
        cache_key = prompt[:200]
        if cache_key in self._refinement_cache:
            return self._refinement_cache[cache_key]

        # Build context summary
        context_summary = self._summarize_context(context)

        # Build refinement prompt
        template = self.config.refinement_prompt_template or self.config._DEFAULT_REFINEMENT_TEMPLATE
        refinement_prompt = template.format(prompt=prompt, context_summary=context_summary)

        try:
            response = self.router.generate(refinement_prompt)
            refined = response.text if hasattr(response, "text") else str(response)
            refined = refined.strip().strip('"').strip("'")

            # Cache the result
            if len(cache_key) > 10:
                self._refinement_cache[cache_key] = refined
                if len(self._refinement_cache) > 500:
                    # Trim cache
                    keys = list(self._refinement_cache.keys())[-250:]
                    self._refinement_cache = {k: self._refinement_cache[k] for k in keys}

            return refined
        except Exception as e:
            logger.warning(f"Prompt refinement failed, using original: {e}")
            return prompt

    def _validate_response(
        self,
        response: str,
        require_json: bool = False,
        require_markdown: bool = False,
        keywords: Optional[list[str]] = None,
        custom_validator: Optional[Callable[[str], tuple[bool, str]]] = None,
    ) -> tuple[bool, str]:
        """Validate an LLM response against configured requirements.

        Args:
            response: The LLM response text
            require_json: If True, check valid JSON
            require_markdown: If True, check markdown formatting
            keywords: Required keywords
            custom_validator: Custom validation function

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not response or not response.strip():
            return False, "Response is empty"

        # JSON validation
        if require_json:
            try:
                json.loads(response)
            except json.JSONDecodeError:
                # Maybe the JSON is wrapped in markdown code block
                json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
                if json_match:
                    try:
                        json.loads(json_match.group(1))
                    except json.JSONDecodeError:
                        return False, "Response is not valid JSON (even after extracting code block)"
                else:
                    return False, "Response is not valid JSON"

        # Markdown validation
        if require_markdown:
            has_headers = bool(re.search(r'^#+\s', response, re.MULTILINE))
            has_list = bool(re.search(r'^[\s]*[-*+]\s', response, re.MULTILINE))
            has_code = bool(re.search(r'```', response))
            if not (has_headers or has_list or has_code):
                return False, "Response does not contain expected markdown formatting"

        # Keyword validation
        if keywords:
            lower_response = response.lower()
            missing = [kw for kw in keywords if kw.lower() not in lower_response]
            if missing:
                return False, f"Response is missing required keywords: {', '.join(missing)}"

        # Custom validation
        if custom_validator:
            try:
                is_valid, error_msg = custom_validator(response)
                if not is_valid:
                    return False, error_msg or "Custom validation failed"
            except Exception as e:
                return False, f"Custom validation error: {e}"

        return True, ""

    def _build_correction_prompt(self, error: str, original: str, attempt: int) -> str:
        """Build a correction prompt for the self-correction loop.

        Args:
            error: The validation error message
            original: The original prompt
            attempt: Current retry attempt number

        Returns:
            Correction prompt for the LLM
        """
        if attempt >= self.config.max_retries:
            guidance = "This is your FINAL attempt. Make sure the response is correct."
        elif attempt >= self.config.max_retries - 1:
            guidance = "Please be very careful this time."
        else:
            guidance = "Please fix the issue and try again."

        return self.config._CORRECTION_TEMPLATE.format(
            error=error,
            additional_guidance=guidance,
            original_prompt=original,
        )

    @staticmethod
    def _summarize_context(context: list[dict], max_tokens: int = 200) -> str:
        """Summarize conversation context for the refinement prompt.

        Args:
            context: List of conversation messages
            max_tokens: Approximate max tokens for summary

        Returns:
            Context summary string
        """
        if not context:
            return "No previous context."

        # Take only the last few messages
        recent = context[-5:] if len(context) > 5 else context
        summary_parts = []
        char_budget = max_tokens * 4  # Rough char estimate

        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if len(content) > 200:
                content = content[:200] + "..."

            entry = f"[{role.capitalize()}]: {content}"
            if len("\n".join(summary_parts + [entry])) > char_budget:
                break
            summary_parts.append(entry)

        return (
            "Recent conversation:\n" + "\n".join(summary_parts[-5:])
            if summary_parts
            else "No previous context."
        )

    def get_stats(self) -> dict:
        """Get optimization statistics.

        Returns:
            Dict with total_processed, success_rate, avg_latency, cache_size
        """
        total = len(self._optimization_history)
        if total == 0:
            return {
                "total_processed": 0,
                "success_rate": 0.0,
                "avg_latency_ms": 0.0,
                "avg_retries": 0.0,
                "cache_size": len(self._refinement_cache),
            }

        successes = sum(1 for r in self._optimization_history if r.valid)
        avg_latency = sum(r.total_latency_ms for r in self._optimization_history) / total
        avg_retries = sum(r.retry_count for r in self._optimization_history) / total

        return {
            "total_processed": total,
            "success_rate": round(successes / total * 100, 1),
            "avg_latency_ms": round(avg_latency, 1),
            "avg_retries": round(avg_retries, 1),
            "cache_size": len(self._refinement_cache),
        }

    def clear_cache(self) -> None:
        """Clear the refinement prompt cache."""
        self._refinement_cache.clear()

    def reset_history(self) -> None:
        """Reset optimization history."""
        self._optimization_history.clear()
