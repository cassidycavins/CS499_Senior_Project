
import re
from dataclasses import dataclass


@dataclass
class StudySource:
    source_id: str
    title: str
    text: str


def split_sentences(text: str) -> list[str]:
    """Split study text into usable sentences."""
    cleaned = " ".join(text.split())
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if len(sentence.strip()) >= 25
    ]


def prepare_sources(
    text: str,
    title: str = "Pasted study material"
) -> list[StudySource]:
    """Standalone input adapter for Steps 13 and 14."""
    if not text.strip():
        raise ValueError("Study material cannot be empty.")

    if len(text) > 20000:
        raise ValueError("Study material exceeds 20,000 characters.")

    return [
        StudySource(
            source_id="manual-1",
            title=title,
            text=text.strip()
        )
    ]


def generate_demo_flashcards(
    sources: list[StudySource],
    count: int = 5
) -> list[dict]:
    """Create demo flashcards without an AI API."""
    cards = []

    for source in sources:
        for sentence in split_sentences(source.text):
            if len(cards) >= count:
                return cards

            cards.append({
                "id": len(cards) + 1,
                "front": "Explain this concept from your notes.",
                "back": sentence,
                "citation": {
                    "source_id": source.source_id,
                    "title": source.title,
                    "excerpt": sentence
                }
            })

    return cards


def generate_demo_quiz(
    sources: list[StudySource],
    count: int = 5
) -> list[dict]:
    """Create clearly labeled demo questions.

    These are not AI-generated questions.
    """
    questions = []

    for source in sources:
        for sentence in split_sentences(source.text):
            if len(questions) >= count:
                return questions

            questions.append({
                "id": len(questions) + 1,
                "question": (
                    "Which statement appears in the study material?"
                ),
                "choices": [
                    sentence,
                    "The material does not discuss this topic.",
                    "No supporting information was provided.",
                    "The source contradicts this statement."
                ],
                "correct_index": 0,
                "explanation": (
                    "The first statement is taken directly "
                    "from the supplied material."
                ),
                "citation": {
                    "source_id": source.source_id,
                    "title": source.title,
                    "excerpt": sentence
                }
            })

    return questions