
from sqlalchemy import text
from app.database import engine

# Assign existing courses to the confirmed student account.
OWNER_ID = 1

with engine.begin() as connection:
    user_exists = connection.execute(
        text("SELECT 1 FROM users WHERE id = :id"),
        {"id": OWNER_ID},
    ).scalar()

    if not user_exists:
        raise RuntimeError("Student account not found.")

    columns = connection.execute(
        text("PRAGMA table_info(courses)")
    ).all()

    if "user_id" not in [column[1] for column in columns]:
        connection.execute(
            text(
                "ALTER TABLE courses "
                "ADD COLUMN user_id INTEGER "
                "REFERENCES users(id)"
            )
        )

    # Assign ownership only to courses without an owner.
    connection.execute(
        text(
            "UPDATE courses SET user_id = :id "
            "WHERE user_id IS NULL"
        ),
        {"id": OWNER_ID},
    )

    connection.execute(
        text(
            "CREATE INDEX IF NOT EXISTS "
            "ix_courses_user_id ON courses(user_id)"
        )
    )

print("Course ownership migration completed.")
