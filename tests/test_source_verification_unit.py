
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.study_tools import source_verifier


SOURCE = (
    "Volume describes the amount of data. "
    "Velocity describes how quickly data is processed."
)


def make_question(
    evidence="Volume describes the amount of data.",
    correct_index=0,
):
    """Create a sample question for verification."""
    return {
        "question": "What does Volume describe?",
        "choices": [
            "Amount of data",
            "Processing speed",
            "Data formats",
            "Data security",
        ],
        "correct_index": correct_index,
        "citation": {"excerpt": evidence},
    }


def make_card(
    front="What does Volume describe?",
    back="The amount of data.",
    evidence="Volume describes the amount of data.",
):
    """Create a sample flashcard for verification."""
    return {
        "front": front,
        "back": back,
        "citation": {"excerpt": evidence},
    }


def mock_verifier(monkeypatch, supported):
    """Mock the Ollama verification response."""
    client = Mock()

    client.chat.return_value = SimpleNamespace(
        message=SimpleNamespace(
            content=json.dumps({
                "supported": supported,
                "explanation": "Test verification result.",
            })
        )
    )

    monkeypatch.setattr(
        source_verifier,
        "get_client",
        lambda: client,
    )

    return client


def test_valid_evidence_context():
    """Find a valid excerpt in source material."""
    context = source_verifier.get_evidence_context(
        "Volume describes the amount of data.",
        SOURCE,
    )

    assert "Volume describes" in context


def test_fabricated_evidence_context():
    """Reject an excerpt missing from the source."""
    context = source_verifier.get_evidence_context(
        "Fabricated information.",
        SOURCE,
    )

    assert context == ""


def test_supported_question(monkeypatch):
    """Accept a source-supported correct answer."""
    client = mock_verifier(monkeypatch, True)

    assert source_verifier.verify_question(
        make_question(), SOURCE
    ) is True

    assert client.chat.call_count == 1


def test_unsupported_question(monkeypatch):
    """Reject an incorrect answer."""
    client = mock_verifier(monkeypatch, False)

    assert source_verifier.verify_question(
        make_question(), SOURCE
    ) is False

    assert client.chat.call_count == 1


def test_question_with_fabricated_citation(monkeypatch):
    """Reject fabricated citations before calling AI."""
    client = mock_verifier(monkeypatch, True)

    question = make_question(
        evidence="This evidence does not exist."
    )

    assert source_verifier.verify_question(
        question, SOURCE
    ) is False

    client.chat.assert_not_called()


def test_invalid_question_answer_index(monkeypatch):
    """Reject indexes outside the answer choices."""
    client = mock_verifier(monkeypatch, True)

    assert source_verifier.verify_question(
        make_question(correct_index=5),
        SOURCE,
    ) is False

    client.chat.assert_not_called()


def test_missing_question_text(monkeypatch):
    """Reject questions with missing text."""
    client = mock_verifier(monkeypatch, True)

    question = make_question()
    question["question"] = ""

    assert source_verifier.verify_question(
        question, SOURCE
    ) is False

    client.chat.assert_not_called()


def test_supported_flashcard(monkeypatch):
    """Accept a supported flashcard answer."""
    client = mock_verifier(monkeypatch, True)

    assert source_verifier.verify_flashcard(
        make_card(), SOURCE
    ) is True

    assert client.chat.call_count == 1


def test_unsupported_flashcard(monkeypatch):
    """Reject an unsupported flashcard answer."""
    client = mock_verifier(monkeypatch, False)

    assert source_verifier.verify_flashcard(
        make_card(), SOURCE
    ) is False

    assert client.chat.call_count == 1


def test_flashcard_with_fabricated_citation(monkeypatch):
    """Reject flashcards with fabricated evidence."""
    client = mock_verifier(monkeypatch, True)

    card = make_card(
        evidence="This evidence does not exist."
    )

    assert source_verifier.verify_flashcard(
        card, SOURCE
    ) is False

    client.chat.assert_not_called()


def test_missing_flashcard_answer(monkeypatch):
    """Reject flashcards without an answer."""
    client = mock_verifier(monkeypatch, True)

    card = make_card(back="")

    assert source_verifier.verify_flashcard(
        card, SOURCE
    ) is False

    client.chat.assert_not_called()


def test_verification_service_failure(monkeypatch):
    """Confirm verification service errors are reported."""
    client = Mock()
    client.chat.side_effect = RuntimeError(
        "Ollama unavailable"
    )

    monkeypatch.setattr(
        source_verifier,
        "get_client",
        lambda: client,
    )

    with pytest.raises(
        RuntimeError,
        match="Ollama unavailable",
    ):
        source_verifier.verify_question(
            make_question(), SOURCE
        )