
import re
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth_service import hash_password

from fastapi import HTTPException
from app.services.auth_service import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/register")
def register_page(request: Request):
    """Display the student registration form."""
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={}
    )


@router.post("/register")
def register_student(
    request: Request,
    name: Annotated[str, Form()],
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    confirm_password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Validate registration and create a student account."""

    name = name.strip()
    email = email.strip().lower()

    def registration_error(message: str):
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "error": message,
                "name": name,
                "email": email,
            },
            status_code=400,
        )

    if not name or len(name) > 150:
        return registration_error("Enter a valid name (1–150 characters).")

    if len(email) > 255 or not re.fullmatch(
        r"[^@\s]+@[^@\s]+\.[^@\s]+", email
    ):
        return registration_error("Enter a valid email address.")

    if len(password) < 12:
        return registration_error(
            "Password must contain at least 12 characters."
        )

    if len(password.encode("utf-8")) > 1024:
        return registration_error("Password is too long.")

    if password != confirm_password:
        return registration_error("Passwords do not match.")

    # Check for an existing account using the normalized email.
    existing_user = db.scalar(
        select(User).where(func.lower(User.email) == email)
    )

    if existing_user:
        return registration_error("An account with this email already exists.")

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
    )

    db.add(user)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return registration_error("An account with this email already exists.")

    # Registration does not automatically authenticate the student.
    return RedirectResponse(
        url="/login?registered=1",
        status_code=303,
    )


@router.get("/login")
def login_page(request: Request):
    """Display the student login form."""
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "registered": request.query_params.get("registered") == "1"
        },
    )


@router.post("/login")
def login_student(
    request: Request,
    email: Annotated[str, Form()],
    password: Annotated[str, Form()],
    db: Annotated[Session, Depends(get_db)],
):
    """Verify credentials and create a student session."""

    email = email.strip().lower()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if user is None or not verify_password(
        password, user.password_hash
    ):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Invalid email or password.",
                "email": email,
            },
            status_code=401,
        )

    # Clear old session data before authenticating.
    request.session.clear()
    request.session["user_id"] = user.id

    return RedirectResponse(
        url="/",
        status_code=303,
    )


@router.post("/logout")
def logout_student(request: Request):
    """End the student's authenticated session."""
    request.session.clear()

    return RedirectResponse(
        url="/login",
        status_code=303,
    )