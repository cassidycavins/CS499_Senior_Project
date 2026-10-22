
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuizAttempt, TopicPerformance
from app.services.performance_service import calculate_quiz_score


def save_quiz_attempt(db: Session, course_id: int, topic_results: dict):
    """Save a completed quiz and its topic-level performance."""

    if not topic_results:
        raise ValueError("Quiz must contain at least one topic.")

    total_correct = 0
    total_questions = 0

    # Validate each topic and calculate the quiz totals.
    for topic, results in topic_results.items():
        if not topic.strip():
            raise ValueError("Topic names cannot be empty.")

        correct = results["correct"]
        total = results["total"]

        calculate_quiz_score(correct, total)

        total_correct += correct
        total_questions += total

    # Calculate the overall score from all topic results.
    score = calculate_quiz_score(total_correct, total_questions)

    quiz_attempt = QuizAttempt(
        course_id=course_id,
        correct_answers=total_correct,
        total_questions=total_questions,
        score=score
    )

    # Add topic performance records to the quiz attempt.
    for topic, results in topic_results.items():
        quiz_attempt.topics.append(
            TopicPerformance(
                topic=topic,
                correct_answers=results["correct"],
                total_questions=results["total"]
            )
        )

    # Commit the quiz and topic records in one transaction.
    try:
        db.add(quiz_attempt)
        db.commit()
        db.refresh(quiz_attempt)
    except Exception:
        db.rollback()
        raise

    return quiz_attempt


def get_quiz_history(db: Session, course_id: int):
    """Retrieve previous quiz attempts for a course."""

    statement = (
        select(QuizAttempt)
        .where(QuizAttempt.course_id == course_id)
        .order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
    )

    return db.scalars(statement).all()


def get_topic_performance(db: Session, course_id: int):
    """Retrieve topic results associated with a course."""

    statement = (
        select(TopicPerformance)
        .join(QuizAttempt)
        .where(QuizAttempt.course_id == course_id)
        .order_by(QuizAttempt.completed_at.desc(), QuizAttempt.id.desc())
    )

    return db.scalars(statement).all()
