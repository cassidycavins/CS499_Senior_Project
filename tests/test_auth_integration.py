import pytest

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, get_db
from app.models import User
from app.routes.auth import router as auth_router
from app.services.auth_dependencies import require_user
from app.services.auth_service import verify_password


EMAIL = "student@example.com"
PASSWORD = "SecurePassword123!"


@pytest.fixture
def auth_setup(tmp_path):
    """Create an isolated authentication test application."""
    database_path = tmp_path / "auth_test.db"

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

    app = FastAPI()

    app.add_middleware(
        SessionMiddleware,
        secret_key="test-only-session-secret",
    )

    # Allow authentication templates to resolve static file URLs.
    app.mount(
        "/static",
        StaticFiles(directory="app/static"),
        name="static",
    )

    app.include_router(auth_router)

    def override_get_db():
        with TestSession() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    @app.get("/test/protected")
    def protected_route(
        user: User = Depends(require_user),
    ):
        """Test access to a login-required endpoint."""
        return {"user_id": user.id, "email": user.email}

    with TestClient(app) as client:
        yield client, TestSession

    app.dependency_overrides.clear()
    engine.dispose()


def register(client, **overrides):
    """Submit registration information."""
    data = {
        "name": "Test Student",
        "email": EMAIL,
        "password": PASSWORD,
        "confirm_password": PASSWORD,
    }
    data.update(overrides)

    return client.post(
        "/register",
        data=data,
        follow_redirects=False,
    )


def login(client, password=PASSWORD, email=EMAIL):
    """Submit student login credentials."""
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )


def test_registration_success(auth_setup):
    """Register a student and verify password storage."""
    client, session_factory = auth_setup

    response = register(client)

    assert response.status_code == 303
    assert response.headers["location"] == (
        "/login?registered=1"
    )

    with session_factory() as db:
        user = db.scalar(
            select(User).where(User.email == EMAIL)
        )

        assert user is not None
        assert user.name == "Test Student"
        assert user.password_hash != PASSWORD
        assert verify_password(
            PASSWORD, user.password_hash
        )


def test_duplicate_registration(auth_setup):
    """Prevent duplicate student accounts."""
    client, session_factory = auth_setup

    register(client)
    response = register(client)

    assert response.status_code == 400
    assert "already exists" in response.text

    with session_factory() as db:
        users = db.scalars(select(User)).all()
        assert len(users) == 1


def test_password_too_short(auth_setup):
    """Reject passwords shorter than 12 characters."""
    client, _ = auth_setup

    response = register(
        client,
        password="short",
        confirm_password="short",
    )

    assert response.status_code == 400
    assert "at least 12 characters" in response.text


def test_password_mismatch(auth_setup):
    """Reject mismatched registration passwords."""
    client, _ = auth_setup

    response = register(
        client,
        confirm_password="DifferentPassword123!",
    )

    assert response.status_code == 400
    assert "Passwords do not match" in response.text


def test_login_success(auth_setup):
    """Verify valid credentials create a session."""
    client, _ = auth_setup

    register(client)
    response = login(client)

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    protected = client.get("/test/protected")

    assert protected.status_code == 200
    assert protected.json()["email"] == EMAIL


def test_incorrect_password(auth_setup):
    """Reject an incorrect password."""
    client, _ = auth_setup

    register(client)
    response = login(
        client,
        password="IncorrectPassword123!",
    )

    assert response.status_code == 401
    assert "Invalid email or password" in response.text

    protected = client.get("/test/protected")
    assert protected.status_code == 401


def test_unknown_email(auth_setup):
    """Reject login attempts for nonexistent accounts."""
    client, _ = auth_setup

    response = login(client)

    assert response.status_code == 401
    assert "Invalid email or password" in response.text


def test_logout_clears_session(auth_setup):
    """Verify logout removes authenticated access."""
    client, _ = auth_setup

    register(client)
    login(client)

    assert client.get("/test/protected").status_code == 200

    response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    assert client.get("/test/protected").status_code == 401


def test_unauthorized_access(auth_setup):
    """Reject protected requests without a login."""
    client, _ = auth_setup

    response = client.get("/test/protected")

    assert response.status_code == 401
    assert response.json()["detail"] == (
        "You must log in to access this feature."
    )