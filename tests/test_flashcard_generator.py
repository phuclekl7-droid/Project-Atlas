"""
Tests for Feature #94: Flashcard Spaced Repetition Generator.
"""

import pytest

from src.core.flashcard_generator import (
    FlashCard,
    FlashcardGenerator,
    _split_into_sentences,
    _extract_key_terms,
    _extract_definitions,
)


class TestFlashCardSM2:
    """Tests for the SM-2 spaced repetition algorithm."""

    def test_new_card_defaults(self):
        card = FlashCard(question="What is Python?", answer="A programming language")
        assert card.ease == 2.5
        assert card.interval == 0
        assert card.repetitions == 0
        assert card.next_review is None

    def test_successful_first_review(self):
        card = FlashCard(question="Q?", answer="A")
        card.update(quality=4)
        assert card.repetitions == 1
        assert card.interval == 1
        assert card.next_review is not None

    def test_successful_second_review(self):
        card = FlashCard(question="Q?", answer="A", repetitions=1, interval=1, ease=2.5)
        card.update(quality=4)
        assert card.repetitions == 2
        assert card.interval == 6

    def test_quality_below_3_resets(self):
        card = FlashCard(question="Q?", answer="A", repetitions=5, interval=30, ease=2.5)
        card.update(quality=1)
        assert card.repetitions == 0
        assert card.interval == 1
        assert card.ease < 2.5

    def test_ease_floor(self):
        card = FlashCard(question="Q?", answer="A", ease=1.3)
        card.update(quality=1)  # Already at floor
        assert card.ease >= 1.3

    def test_perfect_review_increases_ease(self):
        card = FlashCard(question="Q?", answer="A", ease=2.5, repetitions=2, interval=6)
        card.update(quality=5)
        assert card.ease > 2.5
        assert card.interval > 6

    def test_quality_zero_fails(self):
        card = FlashCard(question="Q?", answer="A", repetitions=3, interval=10)
        card.update(quality=0)
        assert card.repetitions == 0
        assert card.interval == 1


class TestSplitIntoSentences:
    """Tests for sentence splitting."""

    def test_simple_sentences(self):
        result = _split_into_sentences("Hello world. This is a test.")
        assert len(result) == 2

    def test_short_sentences_excluded(self):
        result = _split_into_sentences("Hi. Hello. This is a longer sentence.")
        # "Hi" and "Hello" are < 10 chars
        assert len(result) == 1

    def test_empty_text(self):
        assert _split_into_sentences("") == []


class TestExtractKeyTerms:
    """Tests for key term extraction."""

    def test_quoted_terms(self):
        terms = _extract_key_terms('The concept "Machine Learning" is important')
        assert "Machine Learning" in terms

    def test_acronyms(self):
        terms = _extract_key_terms("The API uses JSON format")
        assert "API" in terms
        assert "JSON" in terms

    def test_no_terms(self):
        terms = _extract_key_terms("this is a simple lower case text with no special terms")
        assert len(terms) == 0


class TestExtractDefinitions:
    """Tests for definition extraction."""

    def test_is_definition(self):
        defs = _extract_definitions("Python is a programming language used for web development.")
        assert len(defs) >= 1
        assert defs[0][0].lower().startswith("python")

    def test_refers_to_definition(self):
        defs = _extract_definitions("Machine Learning refers to the study of algorithms.")
        assert len(defs) >= 1
        assert "Machine Learning" in defs[0][0]

    def test_no_definitions(self):
        defs = _extract_definitions("This is just a random sentence without clear definitions.")
        assert len(defs) == 0


class TestFlashcardGenerator:
    """Tests for the FlashcardGenerator class."""

    def test_generate_from_definitions(self):
        generator = FlashcardGenerator()
        text = "Python is a programming language. Machine Learning refers to AI algorithms. API means Application Programming Interface."
        cards = generator.generate_from_text(text)
        assert len(cards) >= 1
        assert any("Python" in c.question for c in cards)
        assert all(c.tags for c in cards)

    def test_generate_q_and_a_simple(self):
        generator = FlashcardGenerator()
        text = "Python is a programming language."
        cards = generator.generate_q_and_a(text)
        assert len(cards) >= 1
        assert cards[0].question.strip().lower() == "python"

    def test_max_cards_limit(self):
        generator = FlashcardGenerator(max_cards=5)
        long_text = "Python is a language. Java is a language. C++ is a language. Ruby is a language. " * 20
        cards = generator.generate_from_text(long_text)
        assert len(cards) <= 5

    def test_generate_from_empty_text(self):
        generator = FlashcardGenerator()
        cards = generator.generate_from_text("")
        assert len(cards) == 0

    def test_generate_from_noise(self):
        generator = FlashcardGenerator()
        cards = generator.generate_from_text("a b c d e f g h i j k l m n o p")
        assert len(cards) == 0

    def test_export_csv(self):
        cards = [
            FlashCard(question="Q1", answer="A1", tags=["tag1"]),
            FlashCard(question="Q2", answer="A2"),
        ]
        generator = FlashcardGenerator()
        csv_data = generator.export_csv(cards)
        assert "Front" in csv_data
        assert "Back" in csv_data
        assert "Q1" in csv_data
        assert "A2" in csv_data

    def test_export_markdown(self):
        cards = [
            FlashCard(question="Q1", answer="A1"),
        ]
        generator = FlashcardGenerator()
        md = generator.export_markdown(cards)
        assert "Generated Flashcards" in md
        assert "Q1" in md
        assert "A1" in md

    def test_get_stats(self):
        generator = FlashcardGenerator()
        assert generator.get_stats()["generated"] == 0
        generator.generate_from_text("Python is a language.")
        assert generator.get_stats()["generated"] >= 1
