
import pytest
from datetime import datetime, timedelta
from app.services.study_session_service import save_study_recommendations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Course, StudySession, User
from app.services.study_session_service import update_study_session_status


@pytest.fixture
def ownership_setup(tmp_path):
    """Create an isolated database with two students."""

    database_path = tmp_path / "ownership_test.db"

    engine = create_engine(
        f"sqlite:///{database_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with TestSession() as db:
        # Create two separate student accounts.
        student1 = User(
            name="Student One",
            email="student1@example.com",
            password_hash="test-hash",
        )

        student2 = User(
            name="Student Two",
            email="student2@example.com",
            password_hash="test-hash",
        )

        db.add_all([student1, student2])
        db.flush()

        course = Course(
            name="Operating Systems",
            code="CS 490",
            user_id=student1.id,
        )

        db.add(course)
        db.flush()

        study_session = StudySession(
            course_id=course.id,
            user_id=student1.id,
            topic="Memory Management",
            topic_score=50.0,
            start_time=__import__("datetime").datetime(
                2026, 11, 20, 10, 0
            ),
            end_time=__import__("datetime").datetime(
                2026, 11, 20, 11, 0
            ),
            status="recommended",
        )

        db.add(study_session)
        db.flush()

        student1_id = student1.id
        student2_id = student2.id
        session_id = study_session.id

        db.commit()

    yield TestSession, student1_id, student2_id, session_id

    engine.dispose()


def test_owner_can_approve_session(ownership_setup):
    """Allow the owner to approve a recommendation."""

    factory, owner_id, _, session_id = ownership_setup

    with factory() as db:
        session = update_study_session_status(
            db, session_id, "approved", owner_id
        )

        assert session is not None
        assert session.status == "approved"


def test_other_student_cannot_approve(ownership_setup):
    """Prevent another student from changing a session."""

    factory, _, other_id, session_id = ownership_setup

    with factory() as db:
        result = update_study_session_status(
            db, session_id, "approved", other_id
        )

        assert result is None

        # Confirm the original recommendation was not changed.
        session = db.get(StudySession, session_id)
        assert session.status == "recommended"


def test_reviewed_session_cannot_be_changed(ownership_setup):
    """Prevent changes after a session has been reviewed."""

    factory, owner_id, _, session_id = ownership_setup

    with factory() as db:
        update_study_session_status(
            db, session_id, "approved", owner_id
        )

        with pytest.raises(ValueError, match="already been reviewed"):
            update_study_session_status(
                db, session_id, "rejected", owner_id
            )

        session = db.get(StudySession, session_id)
        assert session.status == "approved"


def test_overlapping_recommendation_is_not_saved(ownership_setup):
    """Prevent a new session from overlapping an existing one."""
    factory, owner_id, _, session_id = ownership_setup

    with factory() as db:
        existing = db.get(StudySession, session_id)

        # Different topic, but overlaps the existing session.
        recommendation = {
            "course_id": existing.course_id,
            "topic": "Process Scheduling",
            "score": 45.0,
            "start": (existing.start_time + timedelta(minutes=30)).isoformat(),
            "end": (existing.end_time + timedelta(minutes=30)).isoformat(),
        }

        result = save_study_recommendations(
            db, [recommendation], owner_id
        )

        assert result == []
        assert db.query(StudySession).count() == 1


def test_duplicate_pending_topic_is_not_saved(ownership_setup):
    """Reuse an existing pending recommendation for the same topic."""
    factory, owner_id, _, session_id = ownership_setup

    with factory() as db:
        existing = db.get(StudySession, session_id)

        recommendation = {
            "course_id": existing.course_id,
            "topic": existing.topic,
            "score": 50.0,
            "start": (existing.start_time + timedelta(days=1)).isoformat(),
            "end": (existing.end_time + timedelta(days=1)).isoformat(),
        }

        result = save_study_recommendations(
            db, [recommendation], owner_id
        )

        assert len(result) == 1
        assert result[0].id == session_id
        assert db.query(StudySession).count() == 1

def test_non_overlapping_recommendation_is_saved(ownership_setup):
    """Allow a different topic in an available time slot."""
    factory, owner_id, _, session_id = ownership_setup

    with factory() as db:
        existing = db.get(StudySession, session_id)

        recommendation = {
            "course_id": existing.course_id,
            "topic": "Process Scheduling",
            "score": 45.0,
            "start": (existing.end_time + timedelta(hours=1)).isoformat(),
            "end": (existing.end_time + timedelta(hours=2)).isoformat(),
        }

        result = save_study_recommendations(
            db, [recommendation], owner_id
        )

        assert len(result) == 1
        assert result[0].topic == "Process Scheduling"
        assert db.query(StudySession).count() == 2
