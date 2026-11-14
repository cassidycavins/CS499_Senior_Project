
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from app.study_tools import ai_generator


SOURCE = (
    "Volume describes the amount of data. "
    "Velocity describes how quickly data is processed. "
    "Variety describes different forms of data."
)


def make_question(
    question="What does Volume describe?",
    evidence="Volume describes the amount of data.",
    correct_index=0,
    choices=None,
):
    """Create a sample AI-generated question."""
    return {
        "question": question,
        "topic": "Big Data Fundamentals",
        "choices": choices or [
            "Amount of data",
            "Processing speed",
            "Data formats",
            "Data security",
        ],
        "correct_index": correct_index,
        "explanation": "The source defines Volume.",
        "evidence": evidence,
    }


def mock_ollama(monkeypatch, responses):
    """Replace Ollama with predictable responses."""
    client = Mock()

    client.chat.side_effect = [
        SimpleNamespace(
            message=SimpleNamespace(
                content=json.dumps({"questions": questions})
            )
        )
        for questions in responses
    ]

    monkeypatch.setattr(
        ai_generator,
        "Client",
        lambda host: client,
    )

    return client


def test_question_structure_and_answer_index(monkeypatch):
    """Validate generated question fields and answer index."""
    client = mock_ollama(
        monkeypatch,
        [[make_question(correct_index=2)]],
    )

    result = ai_generator.generate_ai_quiz(
        SOURCE, count=1
    )

    assert len(result["questions"]) == 1

    question = result["questions"][0]

    assert question["question"]
    assert question["topic"]
    assert len(question["choices"]) == 4
    assert 0 <= question["correct_index"] <= 3
    assert question["explanation"]
    assert client.chat.call_count == 1


def test_invalid_answer_index(monkeypatch):
    """Reject answer indexes outside the valid range."""
    mock_ollama(
        monkeypatch,
        [[make_question(correct_index=4)]],
    )

    with pytest.raises(ValidationError):
        ai_generator.generate_ai_quiz(SOURCE, count=1)


def test_invalid_choice_count(monkeypatch):
    """Reject questions without exactly four choices."""
    question = make_question()
    question["choices"] = ["A", "B", "C"]

    mock_ollama(monkeypatch, [[question]])

    with pytest.raises(ValidationError):
        ai_generator.generate_ai_quiz(SOURCE, count=1)


def test_duplicate_questions_removed(monkeypatch):
    """Reject repeated questions regardless of casing."""
    first = make_question()
    duplicate = make_question(
        question="  WHAT DOES VOLUME DESCRIBE?  "
    )

    mock_ollama(
        monkeypatch,
        [[first, duplicate]],
    )

    result = ai_generator.generate_ai_quiz(
        SOURCE, count=2
    )

    assert len(result["questions"]) == 1


def test_empty_source_material():
    """Reject blank study material."""
    with pytest.raises(
        ValueError,
        match="Study material cannot be empty",
    ):
        ai_generator.generate_ai_quiz("   ")


def test_invalid_citation_rejected(monkeypatch):
    """Reject evidence that does not exist in the source."""
    question = make_question(
        evidence="This quotation is not in the notes."
    )

    mock_ollama(monkeypatch, [[question]])

    with pytest.raises(
        ValueError,
        match="No generated questions passed",
    ):
        ai_generator.generate_ai_quiz(SOURCE, count=1)


def test_valid_citation_excerpt(monkeypatch):
    """Confirm accepted evidence matches source material."""
    mock_ollama(monkeypatch, [[make_question()]])

    result = ai_generator.generate_ai_quiz(
        SOURCE, count=1
    )

    excerpt = result["questions"][0]["citation"]["excerpt"]

    assert excerpt in SOURCE


def test_generation_failure(monkeypatch):
    """Confirm AI service failures are propagated."""
    client = Mock()
    client.chat.side_effect = RuntimeError(
        "Ollama unavailable"
    )

    monkeypatch.setattr(
        ai_generator,
        "Client",
        lambda host: client,
    )

    with pytest.raises(
        RuntimeError,
        match="Ollama unavailable",
    ):
        ai_generator.generate_ai_quiz(SOURCE, count=1)


def test_fast_mode_skips_ai_verification(monkeypatch):
    """Confirm Fast Mode uses one generation request."""
    client = mock_ollama(
        monkeypatch,
        [[make_question()]],
    )

    result = ai_generator.generate_ai_quiz(
        SOURCE,
        count=1,
        verify=False,
    )

    assert len(result["questions"]) == 1
    assert client.chat.call_count == 1


def test_verified_mode_retries_rejected_question(
    monkeypatch,
):
    """Confirm Verified Mode retries rejected questions."""
    from app.study_tools import source_verifier

    first = make_question()
    second = make_question(
        question="What does Velocity describe?",
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
        "verify_question",
        verifier,
    )

    result = ai_generator.generate_ai_quiz(
        SOURCE,
        count=1,
        verify=True,
    )

    assert len(result["questions"]) == 1
    assert result["questions"][0]["question"] == (
        "What does Velocity describe?"
    )
    assert client.chat.call_count == 2
    assert verifier.call_count == 2