
import argparse
from pathlib import Path

from sqlalchemy import create_engine, text


def migrate(db_path: Path, owner_id: int):
    """Assign existing courses to a specified student account."""

    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    engine = create_engine(f"sqlite:///{db_path.resolve().as_posix()}")

    with engine.begin() as connection:
        # Confirm the student account exists.
        user_exists = connection.execute(
            text("SELECT 1 FROM users WHERE id = :id"),
            {"id": owner_id},
        ).scalar()

        if not user_exists:
            raise RuntimeError("Student account not found.")

        # Add the ownership column if it does not exist.
        columns = connection.execute(
            text("PRAGMA table_info(courses)")
        ).all()

        if "user_id" not in [column[1] for column in columns]:
            connection.execute(
                text(
                    "ALTER TABLE courses "
                    "ADD COLUMN user_id INTEGER REFERENCES users(id)"
                )
            )

        # Assign only courses that have no owner.
        connection.execute(
            text(
                "UPDATE courses SET user_id = :id "
                "WHERE user_id IS NULL"
            ),
            {"id": owner_id},
        )

        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS "
                "ix_courses_user_id ON courses(user_id)"
            )
        )

    engine.dispose()
    print("Course ownership migration completed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("database", type=Path)
    parser.add_argument("owner_id", type=int)
    args = parser.parse_args()

    migrate(args.database, args.owner_id)
