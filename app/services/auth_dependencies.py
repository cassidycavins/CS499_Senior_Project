
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User | None:
    """Return the logged-in student, if one exists."""

    user_id = request.session.get("user_id")

    if user_id is None:
        return None

    user = db.get(User, user_id)

    if user is None:
        request.session.pop("user_id", None)

    return user


def require_user(
    current_user: User | None = Depends(get_current_user)
) -> User:
    """Require a valid student login."""

    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must log in to access this feature."
        )

    return current_user