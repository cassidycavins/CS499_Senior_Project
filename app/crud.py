
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course


# Retrieve all courses
def get_courses(db: Session):
    statement = select(Course).order_by(Course.id)
    return db.scalars(statement).all()


# Retrieve a single course by ID
def get_course(db: Session, course_id: int):
    return db.get(Course, course_id)


# Create and save a new course
def create_course(db: Session, name: str, code: str):
    course = Course(name=name, code=code)

    db.add(course)
    db.commit()
    db.refresh(course)

    return course