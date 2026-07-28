"""
Quick Prompt Templates (Feature: Quick Prompt Templates 1-Click)

Provides a library of curated prompt templates users can 1-click to
quickly populate the chat input without typing.

Each template has: id, title, icon, prompt, category, tags.

Usage:
    library = PromptLibrary()
    templates = library.get_all()
    template = library.get_by_id("code_review")
    prompt_text = library.get_prompt("code_review")
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PromptTemplate:
    """A single prompt template with metadata."""
    id: str
    title: str
    icon: str
    prompt: str
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    description: str = ""


# ── Built-in template catalogue ──

_DEFAULT_TEMPLATES = [
    PromptTemplate(
        id="code_review",
        title="Review & tối ưu code",
        icon="🔍",
        prompt="Hãy review đoạn code sau, chỉ ra lỗi và đề xuất cách tối ưu:\n\n```python\n\n```",
        category="coding",
        tags=["code", "review", "optimize"],
        description="Review code và đề xuất tối ưu",
    ),
    PromptTemplate(
        id="translate_vi",
        title="Dịch sang tiếng Việt",
        icon="🌐",
        prompt="Dịch đoạn văn sau sang tiếng Việt chuẩn văn phong, giữ nguyên ý nghĩa:\n\n",
        category="writing",
        tags=["dịch", "translate", "tiếng Việt"],
        description="Dịch chuẩn văn phong tiếng Việt",
    ),
    PromptTemplate(
        id="unit_test",
        title="Viết Unit Test",
        icon="🧪",
        prompt="Viết unit test bằng pytest cho hàm/thư viện sau. Bao gồm cả test cho edge cases:\n\n```python\n\n```",
        category="coding",
        tags=["test", "pytest", "unit test"],
        description="Tạo pytest unit tests",
    ),
    PromptTemplate(
        id="summary",
        title="Tóm tắt 3 gạch đầu dòng",
        icon="📝",
        prompt="Tóm tắt nội dung sau thành 3 gạch đầu dòng ngắn gọn, súc tích:\n\n",
        category="writing",
        tags=["tóm tắt", "summary", "bullet"],
        description="Tóm tắt ngắn gọn thành bullet points",
    ),
    PromptTemplate(
        id="explain_simple",
        title="Giải thích đơn giản",
        icon="👶",
        prompt="Giải thích khái niệm sau một cách đơn giản nhất, dùng ví dụ thực tế:\n\n",
        category="learning",
        tags=["giải thích", "học tập", "simple"],
        description="Giải thích đơn giản như cho người mới",
    ),
    PromptTemplate(
        id="brainstorm",
        title="Brainstorm ý tưởng",
        icon="💡",
        prompt="Hãy brainstorm các ý tưởng sáng tạo cho chủ đề sau. Đưa ra ít nhất 5 ý tưởng khác nhau:\n\n",
        category="creative",
        tags=["brainstorm", "sáng tạo", "ideas"],
        description="Tạo ý tưởng sáng tạo",
    ),
    PromptTemplate(
        id="fix_bug",
        title="Sửa lỗi code",
        icon="🐛",
        prompt="Đoạn code sau bị lỗi. Hãy tìm nguyên nhân và sửa lỗi:\n\n```python\n\n```",
        category="coding",
        tags=["bug", "fix", "debug"],
        description="Phát hiện và sửa lỗi code",
    ),
    PromptTemplate(
        id="write_email",
        title="Viết email chuyên nghiệp",
        icon="📧",
        prompt="Viết một email chuyên nghiệp bằng tiếng Việt về chủ đề sau:\n\n",
        category="writing",
        tags=["email", "professional", "văn bản"],
        description="Soạn thảo email chuyên nghiệp",
    ),
    PromptTemplate(
        id="improve_writing",
        title="Cải thiện văn bản",
        icon="✍️",
        prompt="Hãy cải thiện đoạn văn sau: sửa lỗi chính tả, ngữ pháp, và làm cho văn phong hay hơn:\n\n",
        category="writing",
        tags=["viết", "cải thiện", "grammar"],
        description="Sửa lỗi và cải thiện văn phong",
    ),
    PromptTemplate(
        id="quiz_me",
        title="Tạo câu hỏi trắc nghiệm",
        icon="❓",
        prompt="Tạo 5 câu hỏi trắc nghiệm (kèm đáp án) về chủ đề sau:\n\n",
        category="learning",
        tags=["quiz", "học tập", "test"],
        description="Tạo câu hỏi trắc nghiệm ôn tập",
    ),
]


class PromptLibrary:
    """
    A curated library of 1-click prompt templates.

    Supports filtering by category and searching by keyword.
    """

    def __init__(self, templates: Optional[list[PromptTemplate]] = None):
        """
        Initialize with built-in templates, optionally extended.

        Args:
            templates: Additional templates to include (merged with defaults)
        """
        self._templates: dict[str, PromptTemplate] = {}
        for t in _DEFAULT_TEMPLATES:
            self._templates[t.id] = t
        if templates:
            for t in templates:
                self._templates[t.id] = t

    @property
    def categories(self) -> list[str]:
        """Get all unique category names."""
        cats: set[str] = set()
        for t in self._templates.values():
            cats.add(t.category)
        return sorted(cats)

    def get_all(self, category: Optional[str] = None) -> list[PromptTemplate]:
        """
        Get all templates, optionally filtered by category.

        Args:
            category: If set, only return templates in this category

        Returns:
            List of PromptTemplate objects
        """
        if category:
            return [t for t in self._templates.values() if t.category == category]
        return list(self._templates.values())

    def get_by_id(self, template_id: str) -> Optional[PromptTemplate]:
        """Get a single template by its ID."""
        return self._templates.get(template_id)

    def get_prompt(self, template_id: str) -> Optional[str]:
        """Get the prompt text for a template by ID."""
        t = self._templates.get(template_id)
        return t.prompt if t else None

    def search(self, query: str) -> list[PromptTemplate]:
        """
        Search templates by title, description, or tags.

        Args:
            query: Search keyword (case-insensitive)

        Returns:
            List of matching templates
        """
        q = query.lower().strip()
        if not q:
            return self.get_all()
        results = []
        for t in self._templates.values():
            if q in t.title.lower() or q in t.description.lower():
                results.append(t)
                continue
            for tag in t.tags:
                if q in tag.lower():
                    results.append(t)
                    break
        return results

    def count(self) -> int:
        """Total number of templates."""
        return len(self._templates)
