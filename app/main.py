from typing import Annotated

from fastapi import FastAPI, Request, Form, HTTPException, Depends, UploadFile, File
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app import crud

from pathlib import Path
from uuid import uuid4

app = FastAPI()

# Configure uploaded study materials
UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Configure HTML templates
templates = Jinja2Templates(directory="app/templates")

# Configure static files
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)


# Display dashboard

@app.get("/")
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)]
):
    courses = crud.get_courses(db)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"courses": courses}
    )


@app.get("/courses/add")
def add_course_form(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add_course.html"
    )


# Process new course submission

@app.post("/courses/add")
def add_course(
    name: Annotated[str, Form()],
    code: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)]
):
    name = name.strip()
    code = code.strip()

    if not name or not code:
        raise HTTPException(
            status_code=400,
            detail="Course name and code are required"
        )

    crud.create_course(
        db=db,
        name=name,
        code=code
    )

    return RedirectResponse(
        url="/",
        status_code=303
    )


# Display individual course page

@app.get("/courses/{course_id}")

# Display individual course page
@app.get("/courses/{course_id}")
def course_detail(
    request: Request,
    course_id: int,
    db: Annotated[Session, Depends(get_db)]
):
    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    # Retrieve uploaded materials for this course
    materials = crud.get_study_materials(db, course_id)

    return templates.TemplateResponse(
        request=request,
        name="course_detail.html",
        context={
            "course": course,
            "materials": materials
        }
    )



# Upload a PDF study material to a course
@app.post("/courses/{course_id}/materials/upload")
async def upload_study_material(
    course_id: int,
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)]
):
    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found"
        )

    original_filename = Path(
        (file.filename or "").replace("\\", "/")
    ).name

    if not original_filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed"
        )

    # Read at most 10 MB plus one byte
    content = await file.read(MAX_FILE_SIZE + 1)

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="PDF file exceeds the 10 MB limit"
        )

    if not content.startswith(b"%PDF-"):
        raise HTTPException(
            status_code=400,
            detail="File does not appear to be a valid PDF"
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
            file_path=str(file_path)
        )
    except Exception:
        file_path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()

    return RedirectResponse(
        url=f"/courses/{course_id}",
        status_code=303
    )
