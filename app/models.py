
from sqlalchemy import Integer, String, ForeignKey, DateTime
from datetime import datetime, timezone
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    code: Mapped[str] = mapped_column(
        String(30),
        nullable=False
    )

    materials: Mapped[list["StudyMaterial"]] = relationship(
        back_populates="course"
    )

class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )

    file_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False
    )

    course: Mapped["Course"] = relationship(
        back_populates="materials"
    )

# Step 15: Quiz performance tracking
class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    course_id: Mapped[int] = mapped_column(
        ForeignKey("courses.id"),
        nullable=False
    )

    correct_answers: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    total_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    score: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    topics: Mapped[list["TopicPerformance"]] = relationship(
        back_populates="quiz_attempt",
        cascade="all, delete-orphan"
    )


class TopicPerformance(Base):
    __tablename__ = "topic_performance"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True
    )

    quiz_attempt_id: Mapped[int] = mapped_column(
        ForeignKey("quiz_attempts.id"),
        nullable=False
    )

    topic: Mapped[str] = mapped_column(
        String(150),
        nullable=False
    )

    correct_answers: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    total_questions: Mapped[int] = mapped_column(
        Integer,
        nullable=False
    )

    quiz_attempt: Mapped["QuizAttempt"] = relationship(
        back_populates="topics"
    )
