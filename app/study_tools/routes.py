
from typing import Annotated
from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
)
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import crud
from app.database import get_db
from app.services.pdf_extractor import extract_text_from_pdf
from .flashcard_generator import generate_ai_flashcards

from .ai_generator import generate_ai_quiz

from .generator import (
    prepare_sources,
)
from .quiz_store import (
    save_quiz,
    get_quiz,
    public_questions,
    grade_quiz,
)


# --------------------------------------------------
# Router and Templates
# --------------------------------------------------

router = APIRouter(
    prefix="/study-tools",
    tags=["Study Tools"],
)

templates = Jinja2Templates(
    directory="app/templates"
)


# --------------------------------------------------
# Request Models
# --------------------------------------------------



class GenerateFromMaterialRequest(BaseModel):
    course_id: int = Field(ge=1)
    material_id: int = Field(ge=1)
    count: int = Field(default=5, ge=1, le=20)
    verify: bool = False


class SubmitQuizRequest(BaseModel):
    quiz_id: str
    answers: dict[str, int] = Field(
        default_factory=dict
    )

def get_pdf_material_text(
    db: Session,
    course_id: int,
    material_id: int,
) -> tuple[str, str]:
    """Retrieve and extract text from an uploaded course PDF."""

    # Verify the course exists.
    course = crud.get_course(db, course_id)

    if course is None:
        raise HTTPException(
            status_code=404,
            detail="Course not found.",
        )

    # Verify the material belongs to the selected course.
    material = crud.get_study_material(db, material_id)

    if material is None or material.course_id != course_id:
        raise HTTPException(
            status_code=404,
            detail="Study material not found for this course.",
        )

    # Only read files stored in the application's uploads directory.
    upload_dir = Path(__file__).resolve().parents[1] / "uploads"
    file_path = Path(material.file_path).resolve()

    if not file_path.is_relative_to(upload_dir.resolve()):
        raise HTTPException(
            status_code=400,
            detail="Invalid study material file path.",
        )

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Uploaded PDF file not found.",
        )

    # Extract PDF text and handle unreadable or scanned files.
    try:
        extracted_text = extract_text_from_pdf(file_path)
    except (ValueError, FileNotFoundError) as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    # Match the maximum input size supported by the AI generators.
    if len(extracted_text) > 20000:
        raise HTTPException(
            status_code=422,
            detail=(
                "This PDF contains more than 20,000 characters. "
                "Please use a shorter PDF for now."
            ),
        )

    return extracted_text, material.filename


# --------------------------------------------------
# Study Tools Page
# --------------------------------------------------

@router.get("/")
def study_tools_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    course_id: int | None = None,
    mode: str = "quiz",
):
    course = None
    materials = []

    if course_id is not None:
        course = crud.get_course(db, course_id)

        if course is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

        # Retrieve uploaded PDFs for the selected course.
        materials = crud.get_study_materials(db, course_id)

    if mode not in ("quiz", "flashcards"):
        raise HTTPException(
            status_code=400,
            detail="Invalid study tool mode",
        )

    return templates.TemplateResponse(
        request=request,
        name="study_tools.html",
        context={
            "course": course,
            "mode": mode,
            "materials": materials,
        },
    )




# --------------------------------------------------
# Generate quiz from uploaded pdf
# --------------------------------------------------

@router.post("/generate-quiz-from-material")
def generate_quiz_from_material(
    request: GenerateFromMaterialRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Generate an AI quiz using an uploaded course PDF."""

    # Retrieve validated PDF text and its original filename.
    text, title = get_pdf_material_text(
        db,
        request.course_id,
        request.material_id,
    )

    try:
        # Reuse the existing source preparation and AI generator.
        sources = prepare_sources(text, title)

        result = generate_ai_quiz(
            text=sources[0].text,
            title=sources[0].title,
            count=request.count,
            verify=request.verify,
        )

        # Store correct answers on the server for secure grading.
        quiz_id = save_quiz(result["questions"])

        return {
            "mode": "ai",
            "quiz_id": quiz_id,
            "questions": public_questions(result["questions"]),
        }

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local AI generation is unavailable. "
                "Make sure Ollama is running and "
                "the configured model is installed."
            ),
        ) from error

@router.post("/submit-quiz")
def submit_quiz(request: SubmitQuizRequest):
    questions = get_quiz(
        request.quiz_id
    )

    if questions is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Quiz not found or expired. "
                "Please generate a new quiz."
            ),
        )

    # Validate question IDs.
    valid_ids = {
        str(question["id"])
        for question in questions
    }

    for question_id in request.answers:
        if question_id not in valid_ids:
            raise HTTPException(
                status_code=422,
                detail="Invalid question ID.",
            )

    # Validate answer choices.
    for answer in request.answers.values():
        if type(answer) is not int or not 0 <= answer <= 3:
            raise HTTPException(
                status_code=422,
                detail="Invalid answer selection.",
            )

    # Calculate score on the backend.
    return grade_quiz(
        questions,
        request.answers,
    )


# --------------------------------------------------
# Generate Flashcards from uploaded pdf
# --------------------------------------------------


@router.post("/generate-flashcards-from-material")
def generate_flashcards_from_material(
    request: GenerateFromMaterialRequest,
    db: Annotated[Session, Depends(get_db)],
):
    """Generate AI flashcards from an uploaded course PDF."""

    # Retrieve validated PDF text and filename.
    text, title = get_pdf_material_text(
        db,
        request.course_id,
        request.material_id,
    )

    try:
        # Reuse the existing source preparation and AI generator.
        sources = prepare_sources(text, title)

        result = generate_ai_flashcards(
            text=sources[0].text,
            title=sources[0].title,
            count=request.count,
            verify=request.verify,
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        ) from error

    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local AI flashcard generation is unavailable. "
                "Check that Ollama is running and "
                "the configured model is installed."
            ),
        ) from error