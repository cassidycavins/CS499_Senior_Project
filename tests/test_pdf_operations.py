
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app import crud
from app.database import Base, get_db
from app.main import app
import app.main as main_module
from app.models import Course, StudyMaterial, User
from app.services.auth_dependencies import require_user


@pytest.fixture
def pdf_test_setup(tmp_path, monkeypatch):
    """Create an isolated database and PDF upload directory."""

    db_path = tmp_path / "pdf_tests.db"
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(
            name="PDF Test Student",
            email="pdf-test@example.com",
            password_hash="test-hash",
        )
        db.add(user)
        db.flush()

        course = Course(
            name="Operating Systems",
            code="CS400",
            user_id=user.id,
        )
        db.add(course)
        db.commit()

        user_id = user.id
        course_id = course.id

    def override_db():
        with Session(engine) as db:
            yield db

    def override_user():
        with Session(engine) as db:
            return db.get(User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_user] = override_user

    # Redirect uploaded files into the temporary directory.
    monkeypatch.setattr(main_module, "UPLOAD_DIR", upload_dir)

    try:
        with TestClient(app) as client:
            yield client, engine, course_id, upload_dir
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(require_user, None)
        engine.dispose()


def upload_pdf(client, course_id, filename, content):
    """Send a file to the application's PDF upload endpoint."""

    return client.post(
        f"/courses/{course_id}/materials/upload",
        files={"file": (filename, content, "application/pdf")},
        follow_redirects=False,
    )


def get_materials(engine, course_id):
    with Session(engine) as db:
        return [
            (material.id, material.filename, material.file_path)
            for material in crud.get_study_materials(db, course_id)
        ]


def test_valid_pdf_upload(pdf_test_setup):
    client, engine, course_id, upload_dir = pdf_test_setup

    content = b"%PDF-1.4\nTest PDF content\n%%EOF"

    response = upload_pdf(client, course_id, "notes.pdf", content)

    assert response.status_code == 303

    materials = get_materials(engine, course_id)
    assert len(materials) == 1
    assert materials[0][1] == "notes.pdf"

    stored_path = Path(materials[0][2])
    assert stored_path.is_file()
    assert stored_path.read_bytes() == content
    assert stored_path.parent == upload_dir


def test_invalid_file_extension(pdf_test_setup):
    client, engine, course_id, upload_dir = pdf_test_setup

    response = upload_pdf(
        client, course_id, "notes.txt", b"Plain text"
    )

    assert response.status_code == 400
    assert get_materials(engine, course_id) == []
    assert list(upload_dir.iterdir()) == []


def test_invalid_pdf_signature(pdf_test_setup):
    client, engine, course_id, upload_dir = pdf_test_setup

    response = upload_pdf(
        client, course_id, "fake.pdf", b"Not a PDF"
    )

    assert response.status_code == 400
    assert get_materials(engine, course_id) == []
    assert list(upload_dir.iterdir()) == []


def test_oversized_pdf(pdf_test_setup):
    client, engine, course_id, upload_dir = pdf_test_setup

    content = b"%PDF-" + b"x" * (main_module.MAX_FILE_SIZE)

    response = upload_pdf(
        client, course_id, "large.pdf", content
    )

    assert response.status_code == 413
    assert get_materials(engine, course_id) == []
    assert list(upload_dir.iterdir()) == []


def test_pdf_persistence(pdf_test_setup):
    client, engine, course_id, upload_dir = pdf_test_setup

    content = b"%PDF-1.4\nPersistent content\n%%EOF"
    response = upload_pdf(client, course_id, "saved.pdf", content)

    assert response.status_code == 303

    # A fresh database session must still find the PDF record.
    materials = get_materials(engine, course_id)

    assert len(materials) == 1
    assert Path(materials[0][2]).read_bytes() == content


def test_pdf_download(pdf_test_setup):
    client, engine, course_id, upload_dir = pdf_test_setup

    content = b"%PDF-1.4\nDownload content\n%%EOF"
    upload_pdf(client, course_id, "download.pdf", content)

    material_id = get_materials(engine, course_id)[0][0]

    response = client.get(
        f"/courses/{course_id}/materials/{material_id}/download"
    )

    assert response.status_code == 200
    assert response.content == content
    assert response.headers["content-type"] == "application/pdf"


def test_pdf_deletion(pdf_test_setup):
    client, engine, course_id, upload_dir = pdf_test_setup

    content = b"%PDF-1.4\nDelete content\n%%EOF"
    upload_pdf(client, course_id, "delete.pdf", content)

    material = get_materials(engine, course_id)[0]
    material_id = material[0]
    stored_path = Path(material[2])

    assert stored_path.exists()

    response = client.post(
        f"/courses/{course_id}/materials/{material_id}/delete",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert not stored_path.exists()
    assert get_materials(engine, course_id) == []
