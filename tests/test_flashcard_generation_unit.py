
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.study_tools import flashcard_generator


SOURCE = (
    "Volume describes the amount of data. "
    "Velocity describes how quickly data is processed. "
    "Variety describes different forms of data."
)


def make_card(
    front="What does Volume describe?",
    back="The amount of data.",
    evidence="Volume describes the amount of data.",
):
    """Create a sample flashcard."""
    return {
        "front": front,
        "back": back,
        "evidence": evidence,
    }


def mock_ollama(monkeypatch, responses):
    """Replace Ollama with predictable responses."""
    client = Mock()

    client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(
                content=json.dumps({"flashcards": cards})
            )
        )
        for cards in responses
    ]

    monkeypatch.setattr(
        flashcard_generator,
        "Client",
        lambda host: client,
    )

    return client


def test_flashcard_structure(monkeypatch):
    """Verify generated flashcard fields."""
    client = mock_ollama(
        monkeypatch,
        [[make_card()]],
    )

    result = flashcard_generator.generate_ai_flashcards(
        SOURCE, count=1
    )

    assert result["mode"] == "ai"
    assert len(result["flashcards"]) == 1

    card = result["flashcards"][0]

    assert card["front"].endswith("?")
    assert card["back"]
    assert card["citation"]["excerpt"] in SOURCE
    assert client.chat.call_count == 1


def test_duplicate_flashcards_removed(monkeypatch):
    """Reject duplicate questions regardless of casing."""
    first = make_card()
    duplicate = make_card(
        front="  WHAT DOES VOLUME DESCRIBE?  "
    )

    mock_ollama(
        monkeypatch,
        [[first, duplicate]],
    )

    result = flashcard_generator.generate_ai_flashcards(
        SOURCE, count=2
    )

    assert len(result["flashcards"]) == 1


def test_empty_source_material():
    """Reject empty study material."""
    with pytest.raises(
        ValueError,
        match="Study material cannot be empty",
    ):
        flashcard_generator.generate_ai_flashcards("   ")


def test_invalid_citation_rejected(monkeypatch):
    """Reject evidence not found in the study material."""
    card = make_card(
        evidence="This quotation does not exist."
    )

    mock_ollama(monkeypatch, [[card]])

    with pytest.raises(
        ValueError,
        match="No generated flashcards passed",
    ):
        flashcard_generator.generate_ai_flashcards(
            SOURCE, count=1
        )


def test_missing_flashcard_answer(monkeypatch):
    """Reject flashcards without an answer."""
    card = make_card(back="")

    mock_ollama(monkeypatch, [[card]])

    with pytest.raises(
        ValueError,
        match="No generated flashcards passed",
    ):
        flashcard_generator.generate_ai_flashcards(
            SOURCE, count=1
        )


def test_flashcard_front_requires_question(monkeypatch):
    """Reject flashcards without a question."""
    card = make_card(front="Volume definition")

    mock_ollama(monkeypatch, [[card]])

    with pytest.raises(
        ValueError,
        match="No generated flashcards passed",
    ):
        flashcard_generator.generate_ai_flashcards(
            SOURCE, count=1
        )


def test_generation_failure(monkeypatch):
    """Verify AI service failures are propagated."""
    client = Mock()
    client.chat.side_effect = RuntimeError(
        "Ollama unavailable"
    )

    monkeypatch.setattr(
        flashcard_generator,
        "Client",
        lambda host: client,
    )

    with pytest.raises(
        RuntimeError,
        match="Ollama unavailable",
    ):
        flashcard_generator.generate_ai_flashcards(
            SOURCE, count=1
        )


def test_fast_mode_skips_verification(monkeypatch):
    """Verify Fast Mode uses one generation request."""
    client = mock_ollama(
        monkeypatch,
        [[make_card()]],
    )

    result = flashcard_generator.generate_ai_flashcards(
        SOURCE,
        count=1,
        verify=False,
    )

    assert len(result["flashcards"]) == 1
    assert client.chat.call_count == 1


def test_verified_mode_retries_rejected_card(
    monkeypatch,
):
    """Verify rejected cards are retried."""
    from app.study_tools import source_verifier

    first = make_card()

    second = make_card(
        front="What does Velocity describe?",
        back="How quickly data is processed.",
        evidence=(
            "Velocity describes how quickly "
            "data is processed."
        ),
    )

    client = mock_ollama(
        monkeypatch,
        [[first], [second]],
    )

    verifier = Mock(side_effect=[False, True])

    monkeypatch.setattr(
        source_verifier,
        "verify_flashcard",
        verifier,
    )

    result = flashcard_generator.generate_ai_flashcards(
        SOURCE,
        count=1,
        verify=True,
    )

    assert len(result["flashcards"]) == 1
    assert result["flashcards"][0]["front"] == (
        "What does Velocity describe?"
    )
    assert client.chat.call_count == 2
    assert verifier.call_count == 2