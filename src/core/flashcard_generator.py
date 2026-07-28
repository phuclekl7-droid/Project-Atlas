"""
Flashcard Spaced Repetition Generator (Feature #94).
Generates Anki-compatible flashcards from text documents using the SM-2 algorithm.

Usage:
    generator = FlashcardGenerator()
    cards = generator.generate_from_text("Python is a programming language...")
    csv_data = generator.export_csv(cards)
    with open("flashcards.csv", "w") as f:
        f.write(csv_data)
"""

import csv
import io
import math
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional


@dataclass
class FlashCard:
    """
    A single flashcard with question, answer, and SM-2 scheduling metadata.

    Attributes:
        question: The front of the card
        answer: The back of the card
        tags: List of tags for categorization
        ease: SM-2 ease factor (starting at 2.5)
        interval: Days until next review
        repetitions: Number of successful reviews
        next_review: Next review date (ISO format or None for new cards)
    """

    question: str
    answer: str
    tags: list[str] = field(default_factory=list)
    ease: float = 2.5
    interval: int = 0
    repetitions: int = 0
    next_review: Optional[str] = None

    def update(self, quality: int) -> None:
        """
        Update card scheduling using SM-2 algorithm.

        Args:
            quality: User rating 0-5
                (0=forgot, 1=wrong, 2=hard, 3=okay, 4=easy, 5=perfect)
        """
        if quality < 3:
            # Reset
            self.repetitions = 0
            self.interval = 1
            self.ease = max(1.3, self.ease - 0.2)
        else:
            # Successful recall
            if self.repetitions == 0:
                self.interval = 1
            elif self.repetitions == 1:
                self.interval = 6
            else:
                self.interval = round(self.interval * self.ease)
            self.repetitions += 1
            self.ease = max(1.3, self.ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))

        self.next_review = (datetime.now() + timedelta(days=self.interval)).strftime("%Y-%m-%d")


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def _extract_key_terms(text: str) -> set[str]:
    """Extract potential key terms (capitalized phrases, quoted terms, definitions)."""
    terms = set()
    # Quoted terms
    for match in re.findall(r'"([^"]+)"', text):
        if 3 < len(match) < 100:
            terms.add(match.strip())
    # Acronyms
    for match in re.findall(r'\b[A-Z]{2,}\b', text):
        terms.add(match)
    return terms


def _extract_definitions(text: str) -> list[tuple[str, str]]:
    """Extract potential definition pairs (term: definition)."""
    definitions = []
    # Pattern: "X is Y" or "X refers to Y" or "X means Y"
    def_patterns = [
        r'([A-Z][A-Za-z\s\-]+?)\s+is\s+(?:a|an|the)?\s*([^.!?]+[.!?])',
        r'([A-Z][A-Za-z\s\-]+?)\s+refers?\s+to\s+([^.!?]+[.!?])',
        r'([A-Z][A-Za-z\s\-]+?)\s+means\s+([^.!?]+[.!?])',
        r'([A-Z][A-Za-z\s\-]+?)\s+are\s+(?:the|a|an)?\s*([^.!?]+[.!?])',
    ]
    for pattern in def_patterns:
        for match in re.finditer(pattern, text):
            term = match.group(1).strip()
            definition = match.group(2).strip()
            if 3 < len(term) < 80 and 5 < len(definition) < 300:
                definitions.append((term, definition))
    return definitions


class FlashcardGenerator:
    """
    Generates flashcards from text content using NLP heuristics.

    Methods:
        generate_from_text(text, source="") -> list[FlashCard]
        generate_q_and_a(text, source="") -> list[FlashCard]
        export_csv(cards) -> str
        export_anki_apkg(cards) -> bytes (placeholder)
    """

    def __init__(self, max_cards: int = 50):
        self.max_cards = max_cards
        self._generated_count = 0

    def generate_from_text(self, text: str, source: str = "") -> list[FlashCard]:
        """
        Generate flashcards from text content.

        Uses two strategies:
        1. Extract definition pairs ("X is Y")
        2. Generate question-answer pairs from key sentences

        Args:
            text: Source text content
            source: Optional source filename for tagging

        Returns:
            List of FlashCard objects
        """
        cards: list[FlashCard] = []
        seen_questions: set[str] = set()

        # Strategy 1: Extract definitions
        definitions = _extract_definitions(text)
        for term, definition in definitions:
            if len(cards) >= self.max_cards:
                break
            question = f"What is {term}?"
            answer = definition
            if question not in seen_questions:
                seen_questions.add(question)
                tags = ["definition"]
                if source:
                    tags.append(source)
                cards.append(FlashCard(question=question, answer=answer, tags=tags))

        # Strategy 2: Key terms from quoted phrases
        terms = _extract_key_terms(text)
        for term in terms:
            if len(cards) >= self.max_cards:
                break
            # Find sentence containing this term
            for sent in _split_into_sentences(text):
                if term.lower() in sent.lower() and len(sent) < 300:
                    question = f"What does \"{term}\" mean in context?"
                    if question not in seen_questions:
                        seen_questions.add(question)
                        tags = ["vocabulary"]
                        if source:
                            tags.append(source)
                        cards.append(FlashCard(question=question, answer=sent.strip(), tags=tags))
                    break

        self._generated_count += len(cards)
        return cards

    def generate_q_and_a(self, text: str, source: str = "") -> list[FlashCard]:
        """
        Generate simple Q&A flashcards from definitions.

        Simpler alternative that creates direct question-answer pairs.
        """
        cards: list[FlashCard] = []
        seen: set[str] = set()

        definitions = _extract_definitions(text)
        for term, definition in definitions:
            if len(cards) >= self.max_cards:
                break
            if term not in seen:
                seen.add(term)
                tags = ["q&a"]
                if source:
                    tags.append(source)
                cards.append(FlashCard(
                    question=term.strip(),
                    answer=definition.strip(),
                    tags=tags,
                ))

        self._generated_count += len(cards)
        return cards

    def export_csv(self, cards: list[FlashCard]) -> str:
        """
        Export flashcards as CSV (Anki-compatible format).

        Anki CSV format: front, back, tags
        """
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Front", "Back", "Tags"])
        for card in cards:
            tags_str = " ".join(card.tags) if card.tags else ""
            writer.writerow([card.question, card.answer, tags_str])
        return output.getvalue()

    def export_markdown(self, cards: list[FlashCard]) -> str:
        """Export flashcards as Markdown."""
        lines = ["# 📝 Generated Flashcards", ""]
        for i, card in enumerate(cards, 1):
            tags = f" `{', '.join(card.tags)}`" if card.tags else ""
            lines.extend([
                f"### Card {i}{tags}",
                "",
                f"**Q:** {card.question}",
                "",
                f"**A:** {card.answer}",
                "",
                "---",
                "",
            ])
        return "\n".join(lines)

    def get_stats(self) -> dict:
        return {"generated": self._generated_count}
