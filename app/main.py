
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

# Steps 13–14: AI quizzes and flashcards
from app.study_tools.routes import router as study_tools_router

# Steps 10–12: PDF text extraction
from app.services.pdf_extractor import extract_text_from_pdf


# --------------------------------------------------
# FastAPI Application
# --------------------------------------------------

app = FastAPI()

# Register AI study tools routes
app.include_router(study_tools_router)


# --------------------------------------------------
# Uploaded Study Materials Configuration
# --------------------------------------------------

UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# --------------------------------------------------
# Templates and Static Files
# --------------------------------------------------

templates = Jinja2Templates(
    directory="app/templates"
)

app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static",
)


# --------------------------------------------------
# Dashboard
# --------------------------------------------------

@app.get("/")
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    courses = crud.get_courses(db)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "courses": courses,
        },
    )


# --------------------------------------------------
# Add Course Form
# --------------------------------------------------

@app.get("/courses/add")
def add_course_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add_course.html",
    )


# --------------------------------------------------
# Process New Course Submission
# --------------------------------------------------

@app.post("/courses/add")
def add_course(
    name: Annotated[str, Form()],
    code: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
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


# --------------------------------------------------
# Display Individual Course Page
# --------------------------------------------------

@app.get("/courses/{course_id}")
def course_detail(
    request: Request,
    course_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found",
        )

    # Retrieve uploaded materials for this course
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


# --------------------------------------------------
# Upload PDF Study Material
# --------------------------------------------------

@app.post("/courses/{course_id}/materials/upload")
async def upload_study_material(
    course_id: int,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
):
    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found",
        )

    original_filename = Path(
        (file.filename or "").replace("\\", "/")
    ).name

    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed",
        )

    # Read at most 10 MB plus one byte
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

    # Generate a unique storage filename
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

    return RedirectResponse(
        url=f"/courses/{course_id}",
        status_code=303,
    )


# --------------------------------------------------
# View Uploaded PDF
# --------------------------------------------------

@app.get(
    "/courses/{course_id}/materials/{material_id}/view"
)
def view_study_material(
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
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

    # Prevent access outside the uploads directory
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


# --------------------------------------------------
# Download Uploaded PDF
# --------------------------------------------------

@app.get(
    "/courses/{course_id}/materials/{material_id}/download"
)
def download_study_material(
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
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


# --------------------------------------------------
# Delete Uploaded PDF
# --------------------------------------------------

@app.post(
    "/courses/{course_id}/materials/{material_id}/delete"
)
def delete_study_material(
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
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


# --------------------------------------------------
# Extract and Display PDF Text
# --------------------------------------------------

@app.get(
    "/courses/{course_id}/materials/{material_id}/text"
)
def view_material_text(
    request: Request,
    course_id: int,
    material_id: int,
    db: Annotated[Session, Depends(get_db)],
):
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

    try:
        extracted_text = extract_text_from_pdf(
            file_path
        )

    except (ValueError, FileNotFoundError) as error:
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