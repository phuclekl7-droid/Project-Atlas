"""
Multi-Agent Debate Module (Feature 63)

Orchestrates a debate between two AI agents with opposing viewpoints
on a given topic. Each agent has a distinct role and system prompt.

Flow:
  1. User provides a topic/question
  2. Agent A (Pro) argues for one position
  3. Agent B (Con) argues for the opposing position
  4. Agents rebut each other for configurable rounds
  5. A Judge agent summarizes and provides a balanced conclusion

Usage:
    from src.core.multi_agent_debate import DebateOrchestrator

    orchestrator = DebateOrchestrator(model_router)
    result = await orchestrator.debate("Should AI be regulated?")
"""

import time
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger
from src.model_router import ModelRouter

logger = setup_logger("debate")


# ============================================================
# Data Models
# ============================================================


@dataclass
class DebateRound:
    """A single round of the debate.

    Attributes:
        round_number: Round number (1-based)
        pro_argument: Agent Pro's argument text
        con_argument: Agent Con's argument text
    """

    round_number: int
    pro_argument: str
    con_argument: str


@dataclass
class DebateResult:
    """Complete debate result.

    Attributes:
        topic: The debate topic
        rounds: List of debate rounds
        conclusion: Judge's final summary
        pro_agent_name: Name of the pro agent
        con_agent_name: Name of the con agent
        total_rounds: Number of rounds
        total_calls: Total LLM calls made
        latency_ms: Total execution time
    """

    topic: str
    rounds: list[DebateRound] = field(default_factory=list)
    conclusion: str = ""
    pro_agent_name: str = "Proponent"
    con_agent_name: str = "Opponent"
    total_rounds: int = 0
    total_calls: int = 0
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "pro_agent": self.pro_agent_name,
            "con_agent": self.con_agent_name,
            "total_rounds": self.total_rounds,
            "total_calls": self.total_calls,
            "latency_ms": round(self.latency_ms, 1),
            "rounds": [
                {
                    "round": r.round_number,
                    "pro": r.pro_argument[:200],
                    "con": r.con_argument[:200],
                }
                for r in self.rounds
            ],
            "conclusion": self.conclusion[:500] if self.conclusion else "",
        }


# ============================================================
# Debate Orchestrator
# ============================================================


class DebateOrchestrator:
    """Orchestrates a multi-agent debate on a given topic.

    Usage:
        orch = DebateOrchestrator(model_router)
        result = await orch.debate(
            topic="Should AI be regulated?",
            rounds=2,
            pro_role="Tech Entrepreneur",
            con_role="Ethics Researcher",
        )
        print(result.conclusion)
    """

    def __init__(
        self,
        model_router: ModelRouter,
        rounds: int = 2,
        provider: Optional[str] = None,
    ):
        """Initialize debate orchestrator.

        Args:
            model_router: ModelRouter instance for LLM calls
            rounds: Number of debate rounds (default: 2)
            provider: Optional provider override (e.g. "openai")
        """
        self._router = model_router
        self._default_rounds = rounds
        self._provider = provider
        self._total_calls = 0

    async def debate(
        self,
        topic: str,
        rounds: Optional[int] = None,
        pro_role: str = "Proponent",
        con_role: str = "Opponent",
        pro_stance: str = "ủng hộ",
        con_stance: str = "phản đối",
    ) -> DebateResult:
        """Run a full debate on the given topic.

        Args:
            topic: The debate topic/question
            rounds: Number of back-and-forth rounds
            pro_role: Name/role for the pro agent
            con_role: Name/role for the con agent
            pro_stance: Stance for the pro agent (e.g. "ủng hộ")
            con_stance: Stance for the con agent (e.g. "phản đối")

        Returns:
            DebateResult with all rounds and conclusion
        """
        num_rounds = rounds or self._default_rounds
        start_time = time.time()

        # System prompts for each agent
        pro_prompt = (
            f"Bạn là {pro_role}, một chuyên gia {pro_stance} chủ đề "
            f"\"{topic}\". Hãy đưa ra các lập luận thuyết phục, "
            f"dựa trên dẫn chứng và logic. Phản biện lại các luận điểm đối lập."
        )
        con_prompt = (
            f"Bạn là {con_role}, một chuyên gia {con_stance} chủ đề "
            f"\"{topic}\". Hãy đưa ra các lập luận thuyết phục, "
            f"dựa trên dẫn chứng và logic. Phản biện lại các luận điểm đối lập."
        )

        result = DebateResult(
            topic=topic,
            pro_agent_name=pro_role,
            con_agent_name=con_role,
        )

        history_pro: list[dict] = []
        history_con: list[dict] = []
        last_pro_arg = ""
        last_con_arg = ""

        for r in range(1, num_rounds + 1):
            # Round opening: Pro speaks first
            pro_context = self._build_context(
                topic, pro_role, pro_stance, history_pro, last_con_arg, is_pro=True
            )
            pro_arg = await self._call_agent(pro_context)
            history_pro.append({"role": "assistant", "content": pro_arg})
            last_pro_arg = pro_arg

            # Con responds
            con_context = self._build_context(
                topic, con_role, con_stance, history_con, last_pro_arg, is_pro=False
            )
            con_arg = await self._call_agent(con_context)
            history_con.append({"role": "assistant", "content": con_arg})
            last_con_arg = con_arg

            result.rounds.append(DebateRound(
                round_number=r,
                pro_argument=pro_arg,
                con_argument=con_arg,
            ))

        # Judge's conclusion
        conclusion = await self._judge_conclusion(
            topic, result.rounds, pro_role, con_role
        )
        result.conclusion = conclusion

        result.total_rounds = num_rounds
        result.total_calls = self._total_calls
        result.latency_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Debate completed: {topic} "
            f"({num_rounds} rounds, {self._total_calls} calls, "
            f"{result.latency_ms:.0f}ms)"
        )

        return result

    # ── Internal ──

    def _build_context(
        self,
        topic: str,
        role: str,
        stance: str,
        history: list[dict],
        opponent_last_arg: str,
        is_pro: bool,
    ) -> str:
        """Build context prompt for one agent.

        Args:
            topic: Debate topic
            role: Agent's role name
            stance: Agent's stance description
            history: This agent's argument history
            opponent_last_arg: Opponent's most recent argument
            is_pro: Whether this is the pro agent

        Returns:
            Context prompt string
        """
        parts = [
            f"Bạn là {role}, chuyên gia {stance} chủ đề: \"{topic}\".",
        ]

        if not history and not opponent_last_arg:
            # First round — opening statement
            parts.append(
                f"Hãy đưa ra luận điểm mở đầu của bạn. "
                f"Trình bày 3-5 lý do thuyết phục."
            )
        elif opponent_last_arg:
            parts.append(
                f"Đối thủ của bạn vừa đưa ra luận điểm sau:\n"
                f"---\n{opponent_last_arg[:1500]}\n---\n\n"
                f"Hãy phản biện lại các luận điểm đó và củng cố lập trường của bạn."
            )

        return "\n\n".join(parts)

    async def _call_agent(self, context: str) -> str:
        """Call the LLM for one agent.

        Args:
            context: Context prompt for this agent

        Returns:
            Agent's response text
        """
        self._total_calls += 1

        try:
            if self._provider:
                response = self._router.generate_with_provider(
                    self._provider, context
                )
            else:
                response = self._router.generate(context)

            text = response.text.strip()
            if len(text) < 10:
                text = f"(Agent could not generate a response)"
            return text
        except Exception as e:
            logger.warning(f"Agent call failed: {e}")
            return f"(Error generating response: {str(e)[:100]})"

    async def _judge_conclusion(
        self,
        topic: str,
        rounds: list[DebateRound],
        pro_role: str,
        con_role: str,
    ) -> str:
        """Generate a balanced conclusion from the judge.

        Args:
            topic: Debate topic
            rounds: Completed debate rounds
            pro_role: Pro agent name
            con_role: Con agent name

        Returns:
            Conclusion text
        """
        summary_lines = [f"Chủ đề tranh luận: {topic}\n"]
        for r in rounds:
            summary_lines.append(f"--- Vòng {r.round_number} ---")
            summary_lines.append(f"{pro_role}: {r.pro_argument[:500]}...")
            summary_lines.append(f"{con_role}: {r.con_argument[:500]}...")

        summary_text = "\n\n".join(summary_lines)

        judge_prompt = (
            f"Bạn là một giám khảo trung lập. Hãy phân tích cuộc tranh luận sau "
            f"và đưa ra kết luận cân bằng, tổng hợp các luận điểm chính "
            f"từ cả hai phía.\n\n"
            f"--- Cuộc tranh luận ---\n{summary_text}\n---\n\n"
            f"Kết luận:"
        )

        try:
            if self._provider:
                response = self._router.generate_with_provider(
                    self._provider, judge_prompt
                )
            else:
                response = self._router.generate(judge_prompt)
            self._total_calls += 1
            return response.text.strip()
        except Exception as e:
            return f"(Không thể tạo kết luận: {str(e)[:100]})"
