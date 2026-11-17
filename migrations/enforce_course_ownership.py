
import argparse
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL




def migrate(db_path: Path, owner_email: str):
    """Update an existing database while preserving student data."""

    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    engine = create_engine(
        URL.create("sqlite", database=str(db_path.resolve()))
    )

    try:
        with engine.begin() as connection:
            # Confirm all required base tables exist.
            tables = set(
                connection.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type='table'"
                    )
                ).scalars()
            )

            required = {
                "users",
                "courses",
                "study_sessions",
                "topic_performance",
            }

            if not required.issubset(tables):
                raise RuntimeError(
                    "Database is missing required application tables."
                )

            # Find the intended owner by email, not a hardcoded ID.
            owner_id = connection.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": owner_email},
            ).scalar()

            if owner_id is None:
                raise RuntimeError(
                    "Specified student account was not found."
                )

            # Add only columns that are missing.
            additions = {
                "courses": {
                    "user_id": "INTEGER REFERENCES users(id)",
                },
                "study_sessions": {
                    "user_id": "INTEGER REFERENCES users(id)",
                    "topic_score": "FLOAT",
                    "google_event_id": "VARCHAR(255)",
                },
                "topic_performance": {
                    "topic_score": "FLOAT",
                },
            }

            for table, columns in additions.items():
                existing = {
                    column[1]
                    for column in connection.execute(
                        text(f"PRAGMA table_info({table})")
                    ).all()
                }

                for name, definition in columns.items():
                    if name not in existing:
                        connection.execute(
                            text(
                                f"ALTER TABLE {table} "
                                f"ADD COLUMN {name} {definition}"
                            )
                        )

                        # Prevent assigning unowned courses in multi-user databases.
            user_count = connection.execute(
                text("SELECT COUNT(*) FROM users")
            ).scalar()

            unowned_courses = connection.execute(
                text("SELECT COUNT(*) FROM courses WHERE user_id IS NULL")
            ).scalar()

            if user_count > 1 and unowned_courses > 0:
                raise RuntimeError(
                    "Multiple users have unowned courses. "
                    "Resolve ownership before migrating."
                )

            # Assign only unowned courses to the specified student.
            connection.execute(
                text(
                    "UPDATE courses SET user_id = :owner "
                    "WHERE user_id IS NULL"
                ),
                {"owner": owner_id},
            )

            # Associate unowned sessions with their course owners.
            connection.execute(
                text(
                    """
                    UPDATE study_sessions
                    SET user_id = (
                        SELECT courses.user_id
                        FROM courses
                        WHERE courses.id = study_sessions.course_id
                    )
                    WHERE user_id IS NULL
                    """
                )
            )

            # Refuse to finish if ownership is missing or inconsistent.
            invalid_sessions = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM study_sessions s
                    LEFT JOIN courses c ON c.id = s.course_id
                    WHERE c.id IS NULL
                    OR s.user_id IS NULL
                    OR c.user_id IS NULL
                    OR s.user_id != c.user_id
                    """
                )
            ).scalar()

            if invalid_sessions:
                raise RuntimeError(
                    "Some study sessions have missing or "
                    "inconsistent ownership."
                )

            # Create the course ownership index.
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS "
                    "ix_courses_user_id ON courses(user_id)"
                )
            )

        # Create the Calendar connection table if it does not exist.
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS google_calendar_connections (
                        id INTEGER PRIMARY KEY,
                        user_id INTEGER NOT NULL UNIQUE
                            REFERENCES users(id),
                        encrypted_credentials VARCHAR NOT NULL,
                        updated_at DATETIME NOT NULL
                    )
                    """
                )
            )

        print("Database migration completed successfully.")

    finally:
        engine.dispose()



if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("database", type=Path)
    parser.add_argument("owner_email")

    args = parser.parse_args()

    migrate(args.database, args.owner_email)
