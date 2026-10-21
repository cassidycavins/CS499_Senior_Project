
from typing import Annotated

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

class GenerateRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=20000,
    )
    title: str = Field(
        default="Pasted study material",
        max_length=200,
    )
    count: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class SubmitQuizRequest(BaseModel):
    quiz_id: str
    answers: dict[str, int] = Field(
        default_factory=dict
    )


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

    if course_id is not None:
        course = crud.get_course(db, course_id)

        if course is None:
            raise HTTPException(
                status_code=404,
                detail="Course not found",
            )

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
        },
    )


# --------------------------------------------------
# Generate AI Quiz
# --------------------------------------------------

@router.post("/generate-quiz")
def generate_quiz(request: GenerateRequest):
    try:
        sources = prepare_sources(
            request.text,
            request.title,
        )

        result = generate_ai_quiz(
            text=sources[0].text,
            title=sources[0].title,
            count=request.count,
        )

        # Store the complete quiz on the server,
        # including correct answers and citations.
        quiz_id = save_quiz(
            result["questions"]
        )

        # Only send questions and answer choices
        # to the browser before submission.
        return {
            "mode": "ai",
            "quiz_id": quiz_id,
            "questions": public_questions(
                result["questions"]
            ),
        }

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local AI generation is unavailable. "
                "Make sure Ollama is running and "
                "the configured model is installed."
            ),
        )


# --------------------------------------------------
# Submit and Grade Quiz
# --------------------------------------------------

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
# Generate Demonstration Flashcards
# --------------------------------------------------


@router.post("/generate-flashcards")
def generate_flashcards(request: GenerateRequest):
    try:
        sources = prepare_sources(
            request.text,
            request.title,
        )

        result = generate_ai_flashcards(
            text=sources[0].text,
            title=sources[0].title,
            count=request.count,
        )

        return result

    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=str(error),
        )

    except Exception:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local AI flashcard generation is unavailable. "
                "Check that Ollama is running and "
                "the configured model is installed."
            ),
        )