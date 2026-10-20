
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, StudyMaterial


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


# Create and save an uploaded study material
def create_study_material(
    db: Session,
    course_id: int,
    filename: str,
    file_path: str
):
    material = StudyMaterial(
        course_id=course_id,
        filename=filename,
        file_path=file_path
    )

    db.add(material)
    db.commit()
    db.refresh(material)

    return material


# Retrieve all uploaded materials for a course
def get_study_materials(db: Session, course_id: int):
    statement = (
        select(StudyMaterial)
        .where(StudyMaterial.course_id == course_id)
        .order_by(StudyMaterial.id)
    )

    return db.scalars(statement).all()
