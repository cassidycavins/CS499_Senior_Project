import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, User, StudyMaterial, StudySession
from app.services.auth_dependencies import require_user
from app.study_tools.quiz_store import save_quiz


@pytest.fixture
def isolation_db():
    """Create an isolated database with two student accounts."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

    def override_get_db():
        with SessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    with SessionLocal() as db:
        student_a = User(
            name="Student A",
            email="student_a@example.com",
            password_hash="test-only-hash",
        )
        student_b = User(
            name="Student B",
            email="student_b@example.com",
            password_hash="test-only-hash",
        )

        db.add_all([student_a, student_b])
        db.flush()

        course_b = Course(
            name="Student B Course",
            code="CS499",
            user_id=student_b.id,
        )

        db.add(course_b)
        db.commit()

        student_a_id = student_a.id
        student_b_id = student_b.id
        course_b_id = course_b.id

    try:
        yield SessionLocal, student_a_id, student_b_id, course_b_id
    finally:
        app.dependency_overrides.pop(require_user, None)
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_course_account_isolation(isolation_db):
    """Verify students cannot access another student's course."""
    SessionLocal, student_a_id, student_b_id, course_b_id = isolation_db

    # Simulate Student A's authenticated session.
    def authenticate_student_a():
        with SessionLocal() as db:
            return db.get(User, student_a_id)

    app.dependency_overrides[require_user] = authenticate_student_a

    with TestClient(app) as client:
        response_a = client.get(
            f"/courses/{course_b_id}"
        )

    assert response_a.status_code == 404

    # Switch to Student B, the course owner.
    def authenticate_student_b():
        with SessionLocal() as db:
            return db.get(User, student_b_id)

    app.dependency_overrides[require_user] = authenticate_student_b

    with TestClient(app) as client:
        response_b = client.get(
            f"/courses/{course_b_id}"
        )

    assert response_b.status_code == 200

@pytest.mark.parametrize(
    "method,endpoint",
    [
        ("POST", "/materials/upload"),
        ("GET", "/materials/1/view"),
        ("GET", "/materials/1/download"),
        ("POST", "/materials/1/delete"),
        ("GET", "/materials/1/text"),
    ],
)
def test_pdf_account_isolation(isolation_db, method, endpoint):
    """Prevent students from accessing another student's PDFs."""
    SessionLocal, student_a_id, _, course_b_id = isolation_db

    # Authenticate as Student A, who does not own the course.
    def authenticate_student_a():
        with SessionLocal() as db:
            return db.get(User, student_a_id)

    app.dependency_overrides[require_user] = authenticate_student_a

    url = f"/courses/{course_b_id}{endpoint}"

    with TestClient(app) as client:
        if endpoint == "/materials/upload":
            response = client.post(
                url,
                files={
                    "file": (
                        "test.pdf",
                        b"%PDF-1.4\n%%EOF",
                        "application/pdf",
                    )
                },
            )
        else:
            response = client.request(method, url)

    assert response.status_code == 404

@pytest.mark.parametrize(
    "method,action",
    [
        ("GET", "view"),
        ("GET", "download"),
        ("POST", "delete"),
        ("GET", "text"),
    ],
)
def test_existing_pdf_account_isolation(
    isolation_db, method, action
):
    """Prevent access to another student's stored PDF."""
    SessionLocal, student_a_id, _, course_b_id = isolation_db

    # Create a PDF record owned by Student B's course.
    with SessionLocal() as db:
        from app.models import StudyMaterial

        material = StudyMaterial(
            course_id=course_b_id,
            filename="student_b_notes.pdf",
            file_path="test_student_b_notes.pdf",
        )
        db.add(material)
        db.commit()
        material_id = material.id

    # Authenticate as Student A.
    def authenticate_student_a():
        with SessionLocal() as db:
            return db.get(User, student_a_id)

    app.dependency_overrides[require_user] = authenticate_student_a

    url = (
        f"/courses/{course_b_id}/materials/"
        f"{material_id}/{action}"
    )

    with TestClient(app) as client:
        response = client.request(method, url)

    assert response.status_code == 404

    # Confirm the unauthorized request did not delete the record.
    with SessionLocal() as db:
        assert db.get(StudyMaterial, material_id) is not None

@pytest.mark.parametrize(
    "endpoint",
    [
        "performance",
        "quiz-history",
    ],
)
def test_performance_account_isolation(isolation_db, endpoint):
    """Prevent students from viewing another student's performance."""
    SessionLocal, student_a_id, _, course_b_id = isolation_db

    # Authenticate as Student A, who does not own the course.
    def authenticate_student_a():
        with SessionLocal() as db:
            return db.get(User, student_a_id)

    app.dependency_overrides[require_user] = authenticate_student_a

    url = f"/courses/{course_b_id}/{endpoint}"

    with TestClient(app) as client:
        response = client.get(url)

    assert response.status_code == 404

def test_quiz_submission_account_isolation(isolation_db):
    """Prevent students from submitting another student's quiz."""
    SessionLocal, student_a_id, _, course_b_id = isolation_db

    # Create a quiz associated with Student B's course.
    questions = [
        {
            "id": 1,
            "question": "What is an operating system?",
            "choices": [
                "System software",
                "A web browser",
                "A database",
                "A programming language",
            ],
            "correct_index": 0,
            "explanation": "An OS manages computer resources.",
            "citation": {
                "source": "test.pdf",
                "excerpt": "An OS manages computer resources.",
            },
            "topic": "Operating Systems",
        }
    ]

    quiz_id = save_quiz(questions, course_id=course_b_id)

    # Authenticate as Student A.
    def authenticate_student_a():
        with SessionLocal() as db:
            return db.get(User, student_a_id)

    app.dependency_overrides[require_user] = authenticate_student_a

    payload = {
        "quiz_id": quiz_id,
        "answers": {"1": 0},
    }

    with TestClient(app) as client:
        response = client.post(
            "/study-tools/submit-quiz",
            json=payload,
        )

    assert response.status_code == 404


from datetime import datetime, timedelta, timezone


@pytest.mark.parametrize(
    "action",
    ["approve", "reject"],
)
def test_study_session_account_isolation(isolation_db, action):
    """Prevent students from modifying another student's sessions."""
    SessionLocal, student_a_id, _, course_b_id = isolation_db

    # Create a recommended session for Student B's course.
    with SessionLocal() as db:
        start = datetime.now(timezone.utc) + timedelta(days=1)

        study_session = StudySession(
            course_id=course_b_id,
            topic="Operating Systems",
            topic_score=50.0,
            start_time=start,
            end_time=start + timedelta(minutes=60),
            status="recommended",
        )

        db.add(study_session)
        db.commit()
        session_id = study_session.id

    # Authenticate as Student A.
    def authenticate_student_a():
        with SessionLocal() as db:
            return db.get(User, student_a_id)

    app.dependency_overrides[require_user] = authenticate_student_a

    with TestClient(app) as client:
        response = client.post(
            f"/study-sessions/{session_id}/{action}",
            follow_redirects=False,
        )

    # Student A must not be able to modify Student B's session.
    assert response.status_code == 404

    # Confirm the session status remains unchanged.
    with SessionLocal() as db:
        saved_session = db.get(StudySession, session_id)
        assert saved_session.status == "recommended"


@pytest.mark.parametrize(
    "action, expected_status",
    [
        ("approve", "approved"),
        ("reject", "rejected"),
    ],
)
def test_study_session_owner_can_update(
    isolation_db, action, expected_status
):
    """Allow students to update their own study sessions."""
    SessionLocal, _, student_b_id, course_b_id = isolation_db

    # Create a recommended session owned by Student B.
    with SessionLocal() as db:
        start = datetime.now(timezone.utc) + timedelta(days=1)

        study_session = StudySession(
            course_id=course_b_id,
            topic="Operating Systems",
            topic_score=50.0,
            start_time=start,
            end_time=start + timedelta(minutes=60),
            status="recommended",
        )

        db.add(study_session)
        db.commit()
        session_id = study_session.id

    # Authenticate as the session owner.
    def authenticate_student_b():
        with SessionLocal() as db:
            return db.get(User, student_b_id)

    app.dependency_overrides[require_user] = authenticate_student_b

    with TestClient(app) as client:
        response = client.post(
            f"/study-sessions/{session_id}/{action}",
            follow_redirects=False,
        )

    # The owner should be redirected after a successful update.
    assert response.status_code == 303

    # Verify the correct status was saved.
    with SessionLocal() as db:
        saved_session = db.get(StudySession, session_id)
        assert saved_session.status == expected_status

@pytest.mark.parametrize("action", ["approve", "reject"])
def test_study_session_requires_login(isolation_db, action):
    """Prevent unauthenticated study-session updates."""
    SessionLocal, _, _, course_b_id = isolation_db

    # Create a recommended study session.
    with SessionLocal() as db:
        start = datetime.now(timezone.utc) + timedelta(days=1)

        study_session = StudySession(
            course_id=course_b_id,
            topic="Operating Systems",
            topic_score=50.0,
            start_time=start,
            end_time=start + timedelta(minutes=60),
            status="recommended",
        )

        db.add(study_session)
        db.commit()
        session_id = study_session.id

    # Do not override authentication.
    app.dependency_overrides.pop(require_user, None)

    with TestClient(app) as client:
        response = client.post(
            f"/study-sessions/{session_id}/{action}",
            follow_redirects=False,
        )

    # Login is required to modify a study session.
    assert response.status_code == 401

    # The session must remain unchanged.
    with SessionLocal() as db:
        saved_session = db.get(StudySession, session_id)
        assert saved_session.status == "recommended"
