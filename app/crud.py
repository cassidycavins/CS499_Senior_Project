
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Course, StudyMaterial


# Retrieve courses belonging to the logged-in student.
def get_courses(db: Session, user_id: int):
    statement = (
        select(Course)
        .where(Course.user_id == user_id)
        .order_by(Course.id)
    )
    return db.scalars(statement).all()


# Retrieve a course only if the student owns it.
def get_course(db: Session, course_id: int, user_id: int):
    statement = select(Course).where(
        Course.id == course_id,
        Course.user_id == user_id
    )
    return db.scalar(statement)


# Create a course for the logged-in student.
def create_course(
    db: Session,
    name: str,
    code: str,
    user_id: int
):
    course = Course(
        name=name,
        code=code,
        user_id=user_id
    )

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


# Retrieve one uploaded study material by ID
def get_study_material(
    db: Session,
    material_id: int
):
    return db.get(StudyMaterial, material_id)


# Delete an uploaded study material from the database
def delete_study_material(
    db: Session,
    material: StudyMaterial
):
    db.delete(material)
    db.commit()
