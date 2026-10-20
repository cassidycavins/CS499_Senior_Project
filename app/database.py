
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Store the database in the project root
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "study_planner.db"

from sqlalchemy.engine import URL

DATABASE_URL = URL.create(
    "sqlite",
    database=str(DATABASE_PATH)
)

# Create the SQLite database engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

# Configure database sessions
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False
)

# Base class for database models
class Base(DeclarativeBase):
    pass


# Provide a database session to FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()