
from app.database import SessionLocal
from app import crud
from app.performance_crud import (
    save_quiz_attempt,
    get_quiz_history,
    get_topic_performance
)

# Sample quiz results for testing without the AI generator.
sample_topics = {
    "Memory Management": {"correct": 4, "total": 10},
    "Process Scheduling": {"correct": 8, "total": 10},
    "File Systems": {"correct": 9, "total": 10}
}

db = SessionLocal()

try:
    # Use an existing course to satisfy the database relationship.
    courses = crud.get_courses(db)

    if not courses:
        print("Create a course on the dashboard before running this test.")
    else:
        course_id = courses[0].id

        # Save a sample quiz attempt to SQLite.
        attempt = save_quiz_attempt(
            db=db,
            course_id=course_id,
            topic_results=sample_topics
        )

        print(f"Saved Quiz Attempt ID: {attempt.id}")
        print(f"Quiz Score: {attempt.score}%")

        # Verify the saved attempt appears in course history.
        history = get_quiz_history(db, course_id)
        print(f"Quiz Attempts Found: {len(history)}")

        # Verify that topic results were also saved.
        topics = get_topic_performance(db, course_id)
        print(f"Topic Records Found: {len(topics)}")

finally:
    db.close()
