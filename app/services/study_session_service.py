
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, StudySession


def save_study_recommendations(
    db: Session,
    recommendations: list[dict],
) -> list[StudySession]:
    """Save new recommendations without duplicating existing sessions."""

    saved_sessions = []

    for recommendation in recommendations:
        course_id = recommendation["course_id"]
        topic = recommendation["topic"]
        start = datetime.fromisoformat(recommendation["start"])
        end = datetime.fromisoformat(recommendation["end"])

        # Check for an existing recommendation with the same details.
        statement = select(StudySession).where(
            StudySession.course_id == course_id,
            StudySession.topic == topic,
            StudySession.start_time == start,
            StudySession.end_time == end,
        )

        existing_session = db.scalar(statement)

        if existing_session:
            saved_sessions.append(existing_session)
            continue

        # Save new sessions with the existing model's status convention.
        session = StudySession(
            course_id=course_id,
            topic=topic,
            topic_score=recommendation.get("score"),
            start_time=start,
            end_time=end,
            status="recommended",
        )

        db.add(session)
        saved_sessions.append(session)

    db.commit()

    return saved_sessions



def update_study_session_status(
    db: Session,
    session_id: int,
    new_status: str,
    user_id: int,
) -> StudySession | None:
    """Update a study session only if the student owns it."""

    if new_status not in {"approved", "rejected"}:
        raise ValueError("Invalid study session status.")

    # Find the session through a course owned by the student.
    statement = (
        select(StudySession)
        .join(Course, StudySession.course_id == Course.id)
        .where(
            StudySession.id == session_id,
            Course.user_id == user_id,
        )
    )

    session = db.scalar(statement)

    if session is None:
        return None

    # Prevent changes to sessions already reviewed.
    if session.status != "recommended":
        raise ValueError("This session has already been reviewed.")

    session.status = new_status
    db.commit()
    db.refresh(session)

    return session
