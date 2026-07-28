"""
Task Planning Agent (ReAct) — Feature 61

Breaks complex user questions into sub-tasks and executes them
sequentially using the ReAct (Reasoning + Acting) framework.

The agent:
  1. Analyzes the user's question
  2. Decomposes it into a step-by-step plan (Plan phase)
  3. Executes each step by calling the model (Act phase)
  4. Reflects on intermediate results (Observe phase)
  5. Returns the final consolidated answer
"""

import re
import time
from typing import Optional

from src.core import setup_logger
from src.model_router import ModelRouter

logger = setup_logger("task_planner")

# Regex to extract step markers from model output
_STEP_PATTERN = re.compile(r'(?:Step|Bước)\s*(\d+)[:\].]\s*(.+)', re.IGNORECASE)


def decompose_question(model_router: ModelRouter, question: str) -> list[str]:
    """Ask the model to decompose a complex question into a plan.

    Args:
        model_router: The ModelRouter instance
        question: The user's complex question

    Returns:
        List of sub-task descriptions
    """
    import asyncio

    decompose_prompt = (
        f"Hãy phân tích câu hỏi sau và chia nó thành các bước nhỏ (tối đa 5 bước) "
        f"để trả lời một cách đầy đủ và chính xác.\n\n"
        f"Câu hỏi: {question}\n\n"
        f"Hãy trả lời theo định dạng:\n"
        f"Bước 1: [Mô tả bước 1]\n"
        f"Bước 2: [Mô tả bước 2]\n"
        f"...\n"
        f"Chỉ liệt kê các bước, không cần giải thích thêm."
    )

    try:
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            model_router.generate_async(decompose_prompt, use_cache=False)
        )
        plan_text = response.text.strip()

        # Parse steps from the response
        steps = []
        for match in _STEP_PATTERN.finditer(plan_text):
            steps.append(match.group(2).strip())

        if not steps:
            # Fallback: treat entire response as one step
            steps = [plan_text]

        logger.info(f"Decomposed question into {len(steps)} steps")
        return steps

    except Exception as e:
        logger.warning(f"Failed to decompose question: {e}")
        return [question]  # Fallback: treat entire question as one step


def execute_step(model_router: ModelRouter, step: str, context: str = "") -> str:
    """Execute a single step using the model.

    Args:
        model_router: The ModelRouter instance
        step: The step description
        context: Previous step results to inform this step

    Returns:
        The step result text
    """
    import asyncio

    if context:
        prompt = (
            f"Đây là kết quả từ các bước trước:\n{context}\n\n"
            f"Bây giờ hãy thực hiện bước sau:\n{step}\n\n"
            f"Chỉ trả lời kết quả của bước này."
        )
    else:
        prompt = step

    try:
        loop = asyncio.get_event_loop()
        response = loop.run_until_complete(
            model_router.generate_async(prompt, use_cache=False)
        )
        return response.text.strip()
    except Exception as e:
        logger.warning(f"Failed to execute step: {e}")
        return f"[Lỗi khi thực hiện bước: {e}]"


def run_task_plan(
    model_router: ModelRouter,
    question: str,
    max_steps: int = 5,
) -> dict:
    """Run the full ReAct task planning pipeline.

    Args:
        model_router: The ModelRouter instance
        question: The user's complex question
        max_steps: Maximum number of decomposition steps

    Returns:
        Dict with keys: question, steps, results, final_answer, latency_ms
    """
    start_time = time.time()

    # Phase 1: Decompose
    steps = decompose_question(model_router, question)
    steps = steps[:max_steps]

    # Phase 2: Execute each step with context
    results = []
    context = ""
    for i, step in enumerate(steps, 1):
        step_result = execute_step(model_router, step, context)
        results.append({"step": i, "description": step, "result": step_result})
        context += f"\nBước {i}: {step_result}\n"

    # Phase 3: Synthesize final answer
    summary_context = "\n".join(
        f"Bước {r['step']}: {r['result']}" for r in results
    )
    synthesis_prompt = (
        f"Dựa trên các kết quả từng bước dưới đây, hãy tổng hợp "
        f"câu trả lời cuối cùng cho câu hỏi gốc.\n\n"
        f"Câu hỏi gốc: {question}\n\n"
        f"Kết quả từng bước:\n{summary_context}\n\n"
        f"Câu trả lời cuối cùng:"
    )

    import asyncio
    try:
        loop = asyncio.get_event_loop()
        final_response = loop.run_until_complete(
            model_router.generate_async(synthesis_prompt, use_cache=False)
        )
        final_answer = final_response.text.strip()
    except Exception as e:
        final_answer = context

    elapsed = (time.time() - start_time) * 1000

    return {
        "question": question,
        "steps": steps,
        "results": results,
        "final_answer": final_answer,
        "latency_ms": round(elapsed, 0),
        "num_steps": len(steps),
    }
