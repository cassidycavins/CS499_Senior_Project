
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, StudySession


def save_study_recommendations(
    db: Session,
    recommendations: list[dict],
    user_id: int,
) -> list[StudySession]:
    """Save new recommendations without duplicating existing sessions."""

    saved_sessions = []

    for recommendation in recommendations:
        course_id = recommendation["course_id"]
        topic = recommendation["topic"]
        start = datetime.fromisoformat(recommendation["start"])
        end = datetime.fromisoformat(recommendation["end"])

        # Only save recommendations for courses owned by this student.
        course = db.scalar(
            select(Course).where(
                Course.id == course_id,
                Course.user_id == user_id,
            )
        )

        if course is None:
            raise ValueError("Course not found or access denied.")

        # Avoid creating another pending recommendation for the same topic.
        existing_topic = db.scalar(
            select(StudySession).where(
                StudySession.user_id == user_id,
                StudySession.course_id == course_id,
                StudySession.topic == topic,
                StudySession.status == "recommended",
            )
        )

        if existing_topic is not None:
            saved_sessions.append(existing_topic)
            continue

        # Reject overlapping pending or approved study sessions.
        conflicting_session = db.scalar(
            select(StudySession).where(
                StudySession.user_id == user_id,
                StudySession.status.in_(["recommended", "approved"]),
                StudySession.start_time < end,
                StudySession.end_time > start,
            )
        )

        if conflicting_session is not None:
            continue

        # Save new sessions with the existing model's status convention.
        session = StudySession(
            user_id=user_id,
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

    # Verify both the session owner and course owner.
    statement = (
        select(StudySession)
        .join(Course, StudySession.course_id == Course.id)
        .where(
            StudySession.id == session_id,
            StudySession.user_id == user_id,
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