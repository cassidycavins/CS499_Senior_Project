"""Offline tests: encrypted credentials and calendar operations are user-scoped."""
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import User, Course, StudySession, GoogleCalendarConnection
from app.google_calendar.credential_storage import (
    save_user_credentials, get_user_credentials, delete_user_credentials,
)
from app.google_calendar import service


@pytest.fixture
def calendar_db(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_TOKEN_ENCRYPTION_KEY", Fernet.generate_key().decode())
    engine = create_engine(f"sqlite:///{tmp_path / 'calendar.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as db:
        db.add_all([
            User(name="A", email="a@test.example", password_hash="hash"),
            User(name="B", email="b@test.example", password_hash="hash"),
        ])
        db.commit()
        yield db
    engine.dispose()


def test_tokens_are_encrypted_and_student_specific(calendar_db):
    db = calendar_db
    save_user_credentials(db, 1, {"token": "secret-a"})
    save_user_credentials(db, 2, {"token": "secret-b"})
    assert get_user_credentials(db, 1) == {"token": "secret-a"}
    assert get_user_credentials(db, 2) == {"token": "secret-b"}
    assert "secret-a" not in db.query(GoogleCalendarConnection).filter_by(user_id=1).one().encrypted_credentials
    assert delete_user_credentials(db, 1)
    assert get_user_credentials(db, 1) is None
    assert get_user_credentials(db, 2) == {"token": "secret-b"}


def test_calendar_service_refuses_unconnected_student(calendar_db):
    with pytest.raises(service.CalendarNotConnected):
        service.get_calendar_service(calendar_db, 2)


def test_event_creation_uses_student_service_and_stable_id(calendar_db, monkeypatch):
    from datetime import datetime
    from unittest.mock import MagicMock
    db = calendar_db
    fake_service = MagicMock()
    fake_service.events.return_value.insert.return_value.execute.return_value = {"id": "event123"}
    monkeypatch.setattr(service, "get_calendar_service", lambda session, uid: fake_service if uid == 1 else None)
    session = StudySession(id=42, course_id=3, user_id=1, topic="Networks",
                           start_time=datetime(2026, 11, 25, 10),
                           end_time=datetime(2026, 11, 25, 11), status="recommended")
    assert service.create_study_event(db, 1, session) == "event123"
    first_body = fake_service.events.return_value.insert.call_args.kwargs["body"]
    assert first_body["summary"] == "Study: Networks"
    assert first_body["start"]["dateTime"].endswith("-06:00")
    service.create_study_event(db, 1, session)
    second_body = fake_service.events.return_value.insert.call_args.kwargs["body"]
    assert first_body["id"] == second_body["id"]
