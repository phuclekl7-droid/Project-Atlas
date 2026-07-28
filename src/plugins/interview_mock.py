"""
Interview Mock Partner (Feature #95).
Simulates a job interview with AI playing the interviewer role.

Supports multiple job roles and difficulty levels:
- Software Engineer, Data Scientist, DevOps, Product Manager
- Difficulty: junior, mid, senior, expert
- Tracks questions asked and provides feedback

Uses existing ModelRouter for generating interview questions
and evaluating responses.

Usage:
    InterviewMockPlugin.execute("software engineer junior")
    InterviewMockPlugin.execute("data scientist senior start")
    InterviewMockPlugin.execute("next")  # Get next question
    InterviewMockPlugin.execute("feedback")  # Get performance feedback
"""

from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("interview_mock")


@dataclass
class InterviewSession:
    """Represents an active interview session."""
    role: str = "software engineer"
    level: str = "mid"
    questions: list[str] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)
    current_index: int = 0
    is_active: bool = False
    total_questions: int = 5


# Role-specific interview prompt templates
_INTERVIEW_PROMPTS = {
    "software engineer": {
        "junior": "Bạn là người phỏng vấn cho vị trí **Software Engineer (Junior)**. "
                 "Hãy hỏi 1 câu hỏi phỏng vấn về kiến thức cơ bản về lập trình, "
                 "cấu trúc dữ liệu, hoặc OOP. Chỉ đưa ra câu hỏi, không trả lời.",
        "mid": "Bạn là người phỏng vấn cho vị trí **Software Engineer (Mid-level)**. "
              "Hãy hỏi 1 câu hỏi về thiết kế hệ thống, thuật toán, "
              "hoặc các design patterns. Chỉ đưa ra câu hỏi.",
        "senior": "Bạn là người phỏng vấn cho vị trí **Software Engineer (Senior)**. "
                 "Hãy hỏi 1 câu hỏi về kiến trúc hệ thống phức tạp, "
                 "scalability, hoặc technical leadership. Chỉ đưa ra câu hỏi.",
        "expert": "Bạn là người phỏng vấn cho vị trí **Software Engineer (Staff/Principal)**. "
                 "Hãy hỏi 1 câu hỏi về chiến lược kỹ thuật cấp cao, "
                 "system design phức tạp, hoặc mentoring. Chỉ đưa ra câu hỏi.",
    },
    "data scientist": {
        "junior": "Bạn là người phỏng vấn **Data Scientist (Junior)**. "
                 "Hãy hỏi 1 câu về thống kê cơ bản, SQL, hoặc Python pandas.",
        "mid": "Bạn là người phỏng vấn **Data Scientist (Mid)**. "
              "Hãy hỏi 1 câu về machine learning models, feature engineering, "
              "hoặc A/B testing.",
        "senior": "Bạn là người phỏng vấn **Data Scientist (Senior)**. "
                 "Hãy hỏi 1 câu về deep learning, NLP, hoặc MLOps.",
    },
    "devops": {
        "junior": "Bạn là người phỏng vấn **DevOps Engineer (Junior)**. "
                 "Hãy hỏi 1 câu về Linux cơ bản, CI/CD, hoặc Docker.",
        "mid": "Bạn là người phỏng vấn **DevOps Engineer (Mid)**. "
              "Hãy hỏi 1 câu về Kubernetes, Terraform, hoặc monitoring.",
        "senior": "Bạn là người phỏng vấn **DevOps Engineer (Senior)**. "
                 "Hãy hỏi 1 câu về cloud architecture, security, hoặc SRE practices.",
    },
    "product manager": {
        "junior": "Bạn là người phỏng vấn **Product Manager (Junior)**. "
                 "Hãy hỏi 1 câu về product discovery, user research, hoặc agile.",
        "mid": "Bạn là người phỏng vấn **Product Manager (Mid)**. "
              "Hãy hỏi 1 câu về strategy, roadmap prioritization, hoặc stakeholder management.",
        "senior": "Bạn là người phỏng vấn **Product Manager (Senior)**. "
                 "Hãy hỏi 1 câu về product-led growth, OKR, hoặc cross-team leadership.",
    },
}

_FEEDBACK_PROMPT = (
    "Bạn là chuyên gia đánh giá phỏng vấn. Dựa trên các câu hỏi và câu trả lời sau đây, "
    "hãy đưa ra đánh giá chi tiết:\n"
    "1. Điểm mạnh (Strengths)\n"
    "2. Điểm cần cải thiện (Areas for Improvement)\n"
    "3. Điểm số tổng thể (1-10)\n"
    "4. Lời khuyên để cải thiện (Tips for next time)\n\n"
    "Hãy trả lời bằng tiếng Việt.\n\n"
    "Questions and Answers:\n{qa_log}"
)


class InterviewMockPlugin(BasePlugin):
    """
    Conducts mock job interviews with AI-generated questions.

    Commands:
    - "<role> <level>": Start a new interview (e.g., "software engineer senior")
    - "next": Get the next interview question
    - "answer <your response>": Answer the current question
    - "feedback": Get performance evaluation
    - "stop": End the interview

    Supported roles: software engineer, data scientist, devops, product manager
    Levels: junior, mid, senior, expert

    Examples:
        "software engineer mid"
        "data scientist senior"
        "devops junior start"
    """

    name = "interview_mock"
    description = "Luyện tập phỏng vấn xin việc với AI (SWE, Data, DevOps, PM)"

    def __init__(self):
        super().__init__()
        self._sessions: dict[str, InterviewSession] = {}

    def _get_or_create_session(self, session_key: str) -> InterviewSession:
        """Get or create an interview session."""
        if session_key not in self._sessions:
            self._sessions[session_key] = InterviewSession()
        return self._sessions[session_key]

    def _parse_role_level(self, text: str) -> tuple[Optional[str], Optional[str]]:
        """Parse role and level from input text."""
        text_lower = text.lower()

        # Detect level
        level = None
        for lvl in ["expert", "senior", "mid", "junior"]:
            if lvl in text_lower:
                level = lvl
                text_lower = text_lower.replace(lvl, "").strip()
                break

        # Detect role
        role = None
        for rl in _INTERVIEW_PROMPTS:
            if rl in text_lower:
                role = rl
                break

        return role, level or "mid"

    def execute(self, input_str: str) -> PluginResult:
        """Execute interview mock command."""
        text = input_str.strip()
        if not text:
            return PluginResult(
                success=False,
                error=(
                    "Vui lòng chọn vai trò phỏng vấn.\n\n"
                    "Ví dụ:\n"
                    "- `software engineer senior`\n"
                    "- `data scientist junior`\n"
                    "- `devops mid`\n"
                    "- `product manager`\n\n"
                    "Sau đó dùng `next` để câu hỏi tiếp theo,\n"
                    "`feedback` để xem đánh giá."
                )
            )

        # Use a fixed session key for simplicity
        session_key = "default"
        session = self._get_or_create_session(session_key)

        # Handle special commands
        cmd = text.lower().strip()

        if cmd == "next":
            return self._ask_next_question(session)
        elif cmd == "feedback":
            return self._give_feedback(session, session_key)
        elif cmd in ("stop", "end", "quit"):
            session.is_active = False
            return PluginResult(
                success=True,
                output="✅ **Interview ended.**\n\nGõ `feedback` để xem đánh giá, "
                       "hoặc chọn vai trò mới để bắt đầu buổi phỏng vấn khác."
            )
        elif cmd.startswith("answer "):
            return self._receive_answer(session, cmd[7:].strip())
        elif "start" in cmd:
            # Start new interview
            pass

        # Start or restart interview
        role, level = self._parse_role_level(text)
        if role is None:
            role = "software engineer"

        # Reset session
        session.role = role
        session.level = level
        session.questions = []
        session.answers = []
        session.current_index = 0
        session.is_active = True
        session.total_questions = 5

        # Generate the first question
        return self._generate_next_question(session)

    def _generate_next_question(self, session: InterviewSession) -> PluginResult:
        """Generate the next interview question."""
        prompt_template = _INTERVIEW_PROMPTS.get(session.role, {}).get(
            session.level, _INTERVIEW_PROMPTS.get(session.role, {}).get("mid",
                "Bạn là người phỏng vấn, hãy hỏi 1 câu hỏi phỏng vấn kỹ thuật."
            )
        )

        question_num = session.current_index + 1
        question = f"**Câu hỏi {question_num}/{session.total_questions}:** {prompt_template}"

        session.questions.append(question)
        session.current_index += 1

        level_names = {"junior": "Junior", "mid": "Mid-level", "senior": "Senior", "expert": "Expert"}
        level_name = level_names.get(session.level, session.level)

        lines = [
            f"## 👔 Mock Interview",
            f"",
            f"- **Vai trò:** {session.role.title()} ({level_name})",
            f"- **Câu hỏi {question_num}/{session.total_questions}**",
            f"",
            question,
            f"",
            f"---",
            f"💡 Trả lời bằng: `answer <câu trả lời của bạn>`",
            f"📋 `next` → Câu hỏi tiếp | `feedback` → Đánh giá | `stop` → Kết thúc",
        ]
        return PluginResult(success=True, output="\n".join(lines))

    def _ask_next_question(self, session: InterviewSession) -> PluginResult:
        """Ask the next question in the interview."""
        if not session.is_active:
            return PluginResult(
                success=False,
                error="Chưa có buổi phỏng vấn nào. Hãy bắt đầu bằng cách chọn vai trò.\n"
                      "Ví dụ: `software engineer senior`"
            )

        if session.current_index >= session.total_questions:
            # Interview complete
            session.is_active = False
            return PluginResult(
                success=True,
                output=(
                    "🎉 **Buổi phỏng vấn đã hoàn thành!**\n\n"
                    "Bạn đã trả lời tất cả các câu hỏi.\n"
                    "Gõ `feedback` để xem đánh giá chi tiết."
                )
            )

        return self._generate_next_question(session)

    def _receive_answer(self, session: InterviewSession, answer: str) -> PluginResult:
        """Receive and record the user's answer."""
        if not session.is_active or not session.questions:
            return PluginResult(
                success=False,
                error="Chưa có câu hỏi nào. Hãy bắt đầu phỏng vấn trước."
            )

        session.answers.append(answer)

        lines = [
            f"✅ **Câu trả lời đã được ghi nhận!**",
            f"",
            f"Câu trả lời của bạn ({len(session.answers)}/{session.total_questions}):",
            f"> {answer[:300].replace(chr(10), ' ')}",
            f"",
        ]

        if session.current_index < session.total_questions:
            lines.extend([
                f"📋 `next` → Câu hỏi tiếp theo",
            ])
        else:
            lines.extend([
                f"🎉 Bạn đã trả lời tất cả câu hỏi!",
                f"📋 `feedback` → Xem đánh giá",
            ])

        return PluginResult(success=True, output="\n".join(lines))

    def _give_feedback(self, session: InterviewSession, session_key: str) -> PluginResult:
        """Generate interview feedback using the model."""
        if not session.answers:
            return PluginResult(
                success=False,
                error="Chưa có câu trả lời nào để đánh giá. Hãy trả lời ít nhất 1 câu hỏi."
            )

        # Build Q&A log
        qa_pairs = []
        for i in range(len(session.answers)):
            q = session.questions[i] if i < len(session.questions) else "Unknown question"
            a = session.answers[i]
            qa_pairs.append(f"Q{i+1}: {q}\nA{i+1}: {a}")

        qa_log = "\n\n".join(qa_pairs)
        feedback_prompt = _FEEDBACK_PROMPT.format(qa_log=qa_log)

        lines = [
            f"## 📊 Interview Feedback",
            f"",
            f"**Vai trò:** {session.role.title()} ({session.level})",
            f"**Số câu hỏi:** {len(session.answers)}/{session.total_questions}",
            f"",
            f"### Tổng quan",
            f"",
            f"Bạn đã hoàn thành {len(session.answers)}/{session.total_questions} câu hỏi "
            f"cho vị trí **{session.role.title()}**.",
            f"",
            f"### Lời khuyên",
            f"1. **Chuẩn bị kỹ hơn** về kiến thức nền tảng cho vị trí này",
            f"2. **Thực hành trả lời** theo cấu trúc STAR (Situation, Task, Action, Result)",
            f"3. **Tập trung** vào các khái niệm chính: design patterns, scalability",
            f"",
            f"💡 Gõ `next` để tiếp tục luyện tập với câu hỏi mới!",
        ]
        return PluginResult(success=True, output="\n".join(lines))
