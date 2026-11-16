
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, QuizAttempt, TopicPerformance
from app.study_tools.quiz_store import save_quiz


@pytest.fixture
def test_db():
    """Create an isolated database for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield SessionLocal
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_duplicate_quiz_submission(test_db):
    """Verify that a quiz can only be submitted once."""

    # Create a course in the test database.
    with test_db() as db:
        course = Course(
            name="Duplicate Test",
            code="TEST101",
        )
        db.add(course)
        db.commit()
        db.refresh(course)
        course_id = course.id

    # Create a quiz with one valid question.
    questions = [
        {
            "id": 1,
            "question": "Test question",
            "choices": ["A", "B", "C", "D"],
            "correct_index": 0,
            "explanation": "Test explanation",
            "citation": {
                "source": "test.pdf",
                "excerpt": "Test evidence",
            },
            "topic": "Duplicate Test",
        }
    ]

    quiz_id = save_quiz(questions, course_id=course_id)

    payload = {
        "quiz_id": quiz_id,
        "answers": {"1": 0},
    }

    # Submit the same quiz twice.
    with TestClient(app) as client:
        first = client.post(
            "/study-tools/submit-quiz",
            json=payload,
        )

        second = client.post(
            "/study-tools/submit-quiz",
            json=payload,
        )

    # Verify that only one attempt was saved.
    with test_db() as db:
        attempts = db.query(QuizAttempt).count()
        topics = db.query(TopicPerformance).count()

    assert first.status_code == 200
    assert second.status_code == 409
    assert attempts == 1
    assert topics == 1
