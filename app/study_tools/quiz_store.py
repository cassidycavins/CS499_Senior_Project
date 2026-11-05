
from datetime import datetime, timedelta, timezone
from threading import Lock
from uuid import uuid4


# Temporary in-memory storage for development.
# A database-backed version can be added later.
_quizzes = {}
_lock = Lock()

QUIZ_EXPIRATION_MINUTES = 60


def save_quiz(questions: list[dict], course_id: int) -> str:
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
            "course_id": course_id,
            "expires_at": expires_at,
            "submission_state": "pending",
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

def get_quiz_course_id(quiz_id: str) -> int | None:
    """Return the course ID for a valid, unexpired quiz."""

    with _lock:
        quiz = _quizzes.get(quiz_id)

        if quiz is None:
            return None

        if quiz["expires_at"] <= datetime.now(timezone.utc):
            del _quizzes[quiz_id]
            return None

        return quiz.get("course_id")

def begin_quiz_submission(quiz_id: str) -> bool:
    """Reserve a quiz for one submission."""

    with _lock:
        quiz = _quizzes.get(quiz_id)

        if quiz is None:
            return False

        if quiz["expires_at"] <= datetime.now(timezone.utc):
            del _quizzes[quiz_id]
            return False

        if quiz.get("submission_state", "pending") != "pending":
            return False

        quiz["submission_state"] = "processing"
        return True


def complete_quiz_submission(quiz_id: str) -> None:
    """Mark a successfully saved quiz as completed."""

    with _lock:
        quiz = _quizzes.get(quiz_id)

        if quiz is not None:
            quiz["submission_state"] = "completed"


def cancel_quiz_submission(quiz_id: str) -> None:
    """Allow another attempt if saving performance fails."""

    with _lock:
        quiz = _quizzes.get(quiz_id)

        if quiz is not None and quiz.get("submission_state") == "processing":
            quiz["submission_state"] = "pending"

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