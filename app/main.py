from typing import Annotated

from fastapi import FastAPI, Request, Form, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from sqlalchemy.orm import Session

from app.database import get_db
from app import crud
from app.study_tools.routes import router as study_tools_router

app = FastAPI()
app.include_router(study_tools_router)

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

    return templates.TemplateResponse(
        request=request,
        name="course_detail.html",
        context={"course": course}
    )