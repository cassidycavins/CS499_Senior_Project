
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

app = FastAPI()

# Configure HTML templates
templates = Jinja2Templates(directory="app/templates")

# Configure static files
app.mount(
    "/static",
    StaticFiles(directory="app/static"),
    name="static"
)

# Temporary course storage
courses = [
    {
        "id": 1,
        "name": "Operating Systems",
        "code": "CS 490"
    },
    {
        "id": 2,
        "name": "Network Security",
        "code": "CS 485"
    }
]

# Display dashboard
@app.get("/")
def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"courses": courses}
    )

# Display Add Course page
@app.get("/courses/add")
def add_course_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="add_course.html",
        context={}
    )

# Process new course submission
@app.post("/courses/add")
def add_course(
    name: str = Form(...),
    code: str = Form(...)
):
    name = name.strip()
    code = code.strip()

    if not name or not code:
        return RedirectResponse(
            url="/courses/add",
            status_code=303
        )

    new_course = {
        "id": max((c["id"] for c in courses), default=0) + 1,
        "name": name,
        "code": code
    }

    courses.append(new_course)

    return RedirectResponse(
        url="/",
        status_code=303
    )
