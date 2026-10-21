
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4


# Temporary in-memory storage for development.
# A database-backed version can be added later.
_quizzes = {}
_lock = Lock()

QUIZ_EXPIRATION_MINUTES = 60


def save_quiz(questions: list[dict]) -> str:
    quiz_id = str(uuid4())

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(minutes=QUIZ_EXPIRATION_MINUTES)
    )

    with _lock:
        # Remove expired quizzes.
        now = datetime.now(timezone.utc)

        expired_ids = [
            key
            for key, value in _quizzes.items()
            if value["expires_at"] <= now
        ]

        for key in expired_ids:
            del _quizzes[key]

        _quizzes[quiz_id] = {
            "questions": questions,
            "expires_at": expires_at,
        }

    return quiz_id


def get_quiz(quiz_id: str):
    with _lock:
        quiz = _quizzes.get(quiz_id)

        if quiz is None:
            return None

        if quiz["expires_at"] <= datetime.now(timezone.utc):
            del _quizzes[quiz_id]
            return None

        return quiz["questions"]


def public_questions(questions: list[dict]) -> list[dict]:
    # Only send the information needed to take the quiz.
    # Keep answer keys, explanations, and citations
    # on the server until submission.
    return [
        {
            "id": question["id"],
            "question": question["question"],
            "choices": question["choices"],
        }
        for question in questions
    ]


def grade_quiz(
    questions: list[dict],
    answers: dict[str, int],
) -> dict:
    results = []
    correct_count = 0

    for question in questions:
        question_id = str(question["id"])
        selected_index = answers.get(question_id)

        is_correct = (
            type(selected_index) is int
            and selected_index == question["correct_index"]
        )

        if is_correct:
            correct_count += 1

        results.append({
            "id": question["id"],
            "selected_index": selected_index,
            "correct_index": question["correct_index"],
            "is_correct": is_correct,
            "explanation": question["explanation"],
            "citation": question["citation"],
        })

    total = len(questions)

    return {
        "correct": correct_count,
        "total": total,
        "percentage": round(
            (correct_count / total) * 100
        ) if total else 0,
        "results": results,
    }