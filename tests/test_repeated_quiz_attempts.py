
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.database import Base
from app.models import User, Course
from app.performance_crud import (
    save_quiz_attempt,
    get_quiz_history,
    get_topic_performance,
)


def test_repeated_quiz_attempts_persist(tmp_path):
    """Verify multiple quiz attempts remain saved after reconnecting."""

    # Use a temporary database to protect application data.
    db_path = tmp_path / "repeated_attempts.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:
            # Create a student and a course for the test.
            user = User(
                name="Test Student",
                email="repeated-test@example.com",
                password_hash="test-hash",
            )
            db.add(user)
            db.flush()

            course = Course(
                name="Computer Networks",
                code="CS400",
                user_id=user.id,
            )
            db.add(course)
            db.commit()

            course_id = course.id

            # Save two attempts for the same topic.
            first = save_quiz_attempt(
                db,
                course_id,
                {"Networking": {"correct": 2, "total": 5}},
            )

            first_id = first.id

            second = save_quiz_attempt(
                db,
                course_id,
                {"Networking": {"correct": 4, "total": 5}},
            )

            second_id = second.id

            assert first_id != second_id
            assert first.score == 40
            assert second.score == 80

        # Open a new session to verify database persistence.
        with Session(engine) as db:
            history = get_quiz_history(db, course_id)
            topics = get_topic_performance(db, course_id)

            assert len(history) == 2
            assert {attempt.id for attempt in history} == {
                first_id,
                second_id,
            }

            assert {attempt.score for attempt in history} == {40, 80}

            assert len(topics) == 2

            topic_results = {
                topic.quiz_attempt_id: (
                    topic.topic,
                    topic.correct_answers,
                    topic.total_questions,
                )
                for topic in topics
            }

            assert topic_results[first_id] == ("Networking", 2, 5)
            assert topic_results[second_id] == ("Networking", 4, 5)

    finally:
        engine.dispose()
