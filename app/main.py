from typing import Annotated
from pathlib import Path
from uuid import uuid4

from fastapi import (
    FastAPI,
    Request,
    Form,
    HTTPException,
    Depends,
    UploadFile,
    File,
)

from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app import crud

# Quiz performance tracking
from app.routes.performance import router as performance_router

# AI quizzes and flashcards
from app.study_tools.routes import router as study_tools_router

# PDF text extraction
from app.services.pdf_extractor import extract_text_from_pdf


# Initialize FastAPI and register feature routes.
app = FastAPI()

app.include_router(performance_router)
app.include_router(study_tools_router)


# Configure uploaded study materials.
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# Configure templates and static files.
templates = Jinja2Templates(
    directory="app/templates"
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


@app.get("/")
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Display all courses on the dashboard."""

    courses = crud.get_courses(db)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "courses": courses,
        },
    )


@app.get("/courses/add")
def add_course_form(request: Request):
    """Display the form for creating a course."""

    return templates.TemplateResponse(
        request=request,
        name="add_course.html",
    )


@app.post("/courses/add")
def add_course(
    name: Annotated[str, Form()],
    code: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Validate and save a new course."""

    name = name.strip()
    code = code.strip()

    if not name or not code:
        raise HTTPException(
            status_code=400,
            detail="Course name and code are required",
        )

    crud.create_course(
        db=db,
        name=name,
        code=code,
    )

    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.get("/courses/{course_id}")
def course_detail(
    request: Request,
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Display course information and uploaded materials."""

    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found",
        )

    materials = crud.get_study_materials(
        db,
        course_id,
    )

    return templates.TemplateResponse(
        request=request,
        name="course_detail.html",
        context={
            "course": course,
            "materials": materials,
        },
    )


@app.post("/courses/{course_id}/materials/upload")
async def upload_study_material(
    course_id: int,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
):
    """Validate, store, and register an uploaded PDF."""

    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found",
        )

    # Remove directory components from the uploaded filename.
    original_filename = Path(
        (file.filename or "").replace("\\", "/")
    ).name

    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    # Limit uploads to 10 MB.
    content = await file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="PDF file exceeds the 10 MB limit",
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid PDF",
        )

    # Use a unique filename to prevent naming conflicts.
    stored_filename = f"{uuid4().hex}.pdf"
    file_path = UPLOAD_DIR / stored_filename

    try:
        file_path.write_bytes(content)

        crud.create_study_material(
            db=db,
            course_id=course_id,
            filename=original_filename,
            file_path=str(file_path),
        )

    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    finally:
        await file.close()

    print(
        f"[PDF Upload] Uploaded: {original_filename}"
    )
    print(
        f"[PDF Upload] Stored at: {file_path}"
    )
    print(
        f"[PDF Upload] Size: {len(content)} bytes"
    )

    return RedirectResponse(
        url=f"/courses/{course_id}",
        status_code=303,
    )


@app.get(
    "/courses/{course_id}/materials/{material_id}/view"
)
def view_study_material(
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Open an uploaded PDF in the browser."""

    material = crud.get_study_material(
        db,
        material_id,
    )

    if material is None or material.course_id != course_id:
        raise HTTPException(
            status_code=404,
            detail="Study material not found",
        )

    file_path = Path(material.file_path).resolve()
    upload_directory = UPLOAD_DIR.resolve()

    # Prevent access outside the uploads directory.
    if not file_path.is_relative_to(upload_directory):
        raise HTTPException(
            status_code=403,
            detail="File access denied",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="PDF file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        content_disposition_type="inline",
        filename=material.filename,
    )


@app.get(
    "/courses/{course_id}/materials/{material_id}/download"
)
def download_study_material(
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Download an uploaded PDF."""

    material = crud.get_study_material(
        db,
        material_id,
    )

    if material is None or material.course_id != course_id:
        raise HTTPException(
            status_code=404,
            detail="Study material not found",
        )

    file_path = Path(material.file_path).resolve()
    upload_directory = UPLOAD_DIR.resolve()

    if not file_path.is_relative_to(upload_directory):
        raise HTTPException(
            status_code=403,
            detail="File access denied",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="PDF file not found",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=material.filename,
        content_disposition_type="attachment",
    )


@app.post(
    "/courses/{course_id}/materials/{material_id}/delete"
)
def delete_study_material(
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Delete an uploaded PDF and its database record."""

    material = crud.get_study_material(
        db,
        material_id,
    )

    if material is None or material.course_id != course_id:
        raise HTTPException(
            status_code=404,
            detail="Study material not found",
        )

    file_path = Path(material.file_path).resolve()
    upload_directory = UPLOAD_DIR.resolve()

    if not file_path.is_relative_to(upload_directory):
        raise HTTPException(
            status_code=403,
            detail="File access denied",
        )

    try:
        file_path.unlink(missing_ok=True)

    except OSError:
        raise HTTPException(
            status_code=500,
            detail="Unable to delete the stored PDF",
        )

    crud.delete_study_material(
        db,
        material,
    )

    return RedirectResponse(
        url=f"/courses/{course_id}",
        status_code=303,
    )


@app.get(
    "/courses/{course_id}/materials/{material_id}/text"
)
def view_material_text(
    request: Request,
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    """Extract and display text from an uploaded PDF."""

    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found",
        )

    material = crud.get_study_material(
        db,
        material_id,
    )

    if material is None or material.course_id != course_id:
        raise HTTPException(
            status_code=404,
            detail="Study material not found",
        )

    file_path = Path(material.file_path).resolve()

    # Ensure the PDF belongs to the uploads directory.
    if not file_path.is_relative_to(
        UPLOAD_DIR.resolve()
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid study material path",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Uploaded PDF file not found",
        )

    # Log file information to diagnose extraction failures.
    print(
        f"[PDF Debug] Filename: {material.filename}"
    )
    print(
        f"[PDF Debug] Stored path: {file_path}"
    )
    print(
        f"[PDF Debug] File size: "
        f"{file_path.stat().st_size} bytes"
    )

    try:
        extracted_text = extract_text_from_pdf(
            file_path
        )

        print(
            f"[PDF Debug] Extracted characters: "
            f"{len(extracted_text)}"
        )

    except (ValueError, FileNotFoundError) as error:

        print(
            f"[PDF Debug] Extraction failed: {error}"
        )

        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    return templates.TemplateResponse(
        request=request,
        name="material_text.html",
        context={
            "course": course,
            "material": material,
            "extracted_text": extracted_text,
        },
    )