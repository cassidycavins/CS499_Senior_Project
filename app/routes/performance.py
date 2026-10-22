
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.performance_crud import (
    get_quiz_history,
    get_topic_performance
)
from app.services.performance_service import (
    calculate_average_score,
    calculate_quiz_score,
    classify_performance
)


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def get_course_or_404(db, course_id):
    """Retrieve a course or return a 404 error."""

    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    return course


@router.get("/courses/{course_id}/performance")
def performance_dashboard(
    request: Request,
    course_id: int,
    db: Session = Depends(get_db)
):
    """Display quiz statistics and knowledge gaps for a course."""

    course = get_course_or_404(db, course_id)
    attempts = get_quiz_history(db, course_id)
    topic_records = get_topic_performance(db, course_id)

    # Calculate the average score across completed quizzes.
    scores = [attempt.score for attempt in attempts]
    average_score = (
        calculate_average_score(scores) if scores else None
    )

    # Combine results for topics appearing in multiple quizzes.
    topic_totals = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )

    for record in topic_records:
        topic_totals[record.topic]["correct"] += record.correct_answers
        topic_totals[record.topic]["total"] += record.total_questions

    topic_summary = []

    for topic, results in topic_totals.items():
        score = calculate_quiz_score(
            results["correct"],
            results["total"]
        )

        topic_summary.append({
            "topic": topic,
            "score": score,
            "status": classify_performance(score),
            "needs_review": score < 70
        })

    # Display the weakest topics first.
    topic_summary.sort(key=lambda item: item["score"])

    weak_topics = [
        item for item in topic_summary
        if item["needs_review"]
    ]

    return templates.TemplateResponse(
        request=request,
        name="performance.html",
        context={
            "course": course,
            "attempts": attempts,
            "average_score": average_score,
            "total_attempts": len(attempts),
            "topic_summary": topic_summary,
            "weak_topics": weak_topics
        }
    )


@router.get("/courses/{course_id}/quiz-history")
def quiz_history(
    request: Request,
    course_id: int,
    db: Session = Depends(get_db)
):
    """Display previous quiz attempts for a course."""

    course = get_course_or_404(db, course_id)
    attempts = get_quiz_history(db, course_id)

    return templates.TemplateResponse(
        request=request,
        name="quiz_history.html",
        context={
            "course": course,
            "attempts": attempts
        }
    )
