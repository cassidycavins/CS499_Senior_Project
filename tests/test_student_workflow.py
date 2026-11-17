
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, get_db
from app.main import app
import app.main as main_module
import app.study_tools.routes as study_routes
from app.models import (
    User,
    Course,
    StudyMaterial,
    QuizAttempt,
    TopicPerformance,
)
from app.study_tools import quiz_store


@pytest.fixture
def workflow_setup(tmp_path, monkeypatch):
    """Create isolated storage for the student workflow."""

    db_path = tmp_path / "student_workflow.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    def override_get_db():
        with TestSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    # Keep PDF uploads outside the real application directory.
    monkeypatch.setattr(main_module, "UPLOAD_DIR", upload_dir)

    # The quiz route normally validates files against app/uploads.
    # Replace only PDF text retrieval; retain actual HTTP and DB logic.
    def fake_pdf_material_text(db, course_id, material_id, user_id):
        course = db.get(Course, course_id)
        material = db.get(StudyMaterial, material_id)

        if course is None or course.user_id != user_id:
            raise ValueError("Course access denied")

        if material is None or material.course_id != course_id:
            raise ValueError("Material access denied")

        assert Path(material.file_path).is_file()

        return (
            "A process is a program in execution. "
            "Threads share the resources of their process.",
            material.filename,
        )

    monkeypatch.setattr(
        study_routes,
        "get_pdf_material_text",
        fake_pdf_material_text,
    )

    # Mock Ollama while preserving quiz generation and submission routes.
    def fake_generate_ai_quiz(text, title, count, verify):
        assert count == 3
        assert title == "operating_systems.pdf"

        questions = [
            {
                "id": f"question-{number}",
                "question": f"Question {number}?",
                "choices": ["A", "B", "C", "D"],
                "correct_index": 0,
                "explanation": "Supported by the source.",
                "citation": {
                    "excerpt": "A process is a program in execution."
                },
                "topic": "Processes",
            }
            for number in range(1, 4)
        ]

        return {"questions": questions}

    monkeypatch.setattr(
        study_routes,
        "generate_ai_quiz",
        fake_generate_ai_quiz,
    )

    try:
        with TestClient(app) as client:
            yield client, TestSession, upload_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_complete_student_workflow(workflow_setup):
    """Test registration through saved quiz performance."""

    client, TestSession, upload_dir = workflow_setup

    # Step 1: Register a student.
    response = client.post(
        "/register",
        data={
            "name": "Workflow Student",
            "email": "workflow@example.com",
            "password": "SecurePassword123!",
            "confirm_password": "SecurePassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    # Step 2: Log in using the registered account.
    response = client.post(
        "/login",
        data={
            "email": "workflow@example.com",
            "password": "SecurePassword123!",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    # Step 3: Create a course.
    response = client.post(
        "/courses/add",
        data={
            "name": "Operating Systems",
            "code": "CS400",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    with TestSession() as db:
        user = db.scalar(
            select(User).where(
                User.email == "workflow@example.com"
            )
        )
        assert user is not None

        course = db.scalar(
            select(Course).where(
                Course.user_id == user.id
            )
        )
        assert course is not None
        assert course.name == "Operating Systems"
        course_id = course.id

    # Step 4: Upload a PDF to the student's course.
    pdf_content = b"%PDF-1.4\nTest content\n%%EOF"

    response = client.post(
        f"/courses/{course_id}/materials/upload",
        files={
            "file": (
                "operating_systems.pdf",
                pdf_content,
                "application/pdf",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    with TestSession() as db:
        material = db.scalar(
            select(StudyMaterial).where(
                StudyMaterial.course_id == course_id
            )
        )
        assert material is not None
        material_id = material.id
        assert Path(material.file_path).is_file()
        assert Path(material.file_path).parent == upload_dir

    # Step 5: Generate three quiz questions.
    response = client.post(
        "/study-tools/generate-quiz-from-material",
        json={
            "course_id": course_id,
            "material_id": material_id,
            "count": 3,
            "verify": False,
        },
    )

    assert response.status_code == 200

    quiz = response.json()
    quiz_id = quiz["quiz_id"]

    assert len(quiz["questions"]) == 3

    # Correct answers must not be exposed before submission.
    for question in quiz["questions"]:
        assert "correct_index" not in question

    # Step 6: Submit two correct answers and one incorrect answer.
    answers = {
        str(quiz["questions"][0]["id"]): 0,
        str(quiz["questions"][1]["id"]): 0,
        str(quiz["questions"][2]["id"]): 1,
    }

    response = client.post(
        "/study-tools/submit-quiz",
        json={
            "quiz_id": quiz_id,
            "answers": answers,
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["correct"] == 2
    assert result["total"] == 3
    assert result["percentage"] == 67

    # Step 7: Verify quiz performance was saved to SQLite.
    with TestSession() as db:
        attempt = db.scalar(
            select(QuizAttempt).where(
                QuizAttempt.course_id == course_id
            )
        )

        assert attempt is not None
        assert attempt.correct_answers == 2
        assert attempt.total_questions == 3
        assert attempt.score == 67

        topic = db.scalar(
            select(TopicPerformance).where(
                TopicPerformance.quiz_attempt_id == attempt.id
            )
        )

        assert topic is not None
        assert topic.topic == "Processes"
        assert topic.correct_answers == 2
        assert topic.total_questions == 3

        # Step 8: Verify the performance dashboard displays saved results.
    response = client.get(
        f"/courses/{course_id}/performance"
    )

    assert response.status_code == 200

    # Confirm the completed quiz and weak topic appear on the page.
    assert "Processes" in response.text
    assert "67" in response.text
    # Step 8: Verify the student cannot submit the same quiz twice.
    duplicate = client.post(
        "/study-tools/submit-quiz",
        json={
            "quiz_id": quiz_id,
            "answers": answers,
        },
    )

    assert duplicate.status_code == 409

    # Remove this test's quiz from temporary in-memory storage.
    with quiz_store._lock:
        quiz_store._quizzes.pop(quiz_id, None)
