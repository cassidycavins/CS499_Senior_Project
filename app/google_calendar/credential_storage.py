
import json
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GoogleCalendarConnection
load_dotenv()


def get_encryption_cipher() -> Fernet:
    """Load the encryption key from the environment."""
    key = os.getenv("GOOGLE_TOKEN_ENCRYPTION_KEY")

    if not key:
        raise RuntimeError(
            "GOOGLE_TOKEN_ENCRYPTION_KEY is not configured."
        )

    return Fernet(key.encode())


def encrypt_credentials(credentials: dict) -> str:
    """Encrypt Google OAuth credentials before database storage."""
    cipher = get_encryption_cipher()
    credential_json = json.dumps(credentials)

    return cipher.encrypt(
        credential_json.encode("utf-8")
    ).decode("utf-8")


def decrypt_credentials(encrypted_credentials: str) -> dict:
    """Decrypt stored credentials when accessing Google Calendar."""
    cipher = get_encryption_cipher()

    decrypted_json = cipher.decrypt(
        encrypted_credentials.encode("utf-8")
    )

    return json.loads(decrypted_json.decode("utf-8"))


def save_user_credentials(
    db: Session,
    user_id: int,
    credentials: dict
) -> GoogleCalendarConnection:
    """Save encrypted Google credentials for one student."""
    encrypted = encrypt_credentials(credentials)

    connection = db.scalar(
        select(GoogleCalendarConnection).where(
            GoogleCalendarConnection.user_id == user_id
        )
    )

    if connection is None:
        connection = GoogleCalendarConnection(
            user_id=user_id,
            encrypted_credentials=encrypted
        )
        db.add(connection)
    else:
        connection.encrypted_credentials = encrypted

    db.commit()
    db.refresh(connection)

    return connection


def get_user_credentials(
    db: Session,
    user_id: int
) -> dict | None:
    """Retrieve and decrypt one student's Google credentials."""
    connection = db.scalar(
        select(GoogleCalendarConnection).where(
            GoogleCalendarConnection.user_id == user_id
        )
    )

    if connection is None:
        return None

    return decrypt_credentials(connection.encrypted_credentials)


def delete_user_credentials(
    db: Session,
    user_id: int
) -> bool:
    """Disconnect one student's Google Calendar account."""
    connection = db.scalar(
        select(GoogleCalendarConnection).where(
            GoogleCalendarConnection.user_id == user_id
        )
    )

    if connection is None:
        return False

    db.delete(connection)
    db.commit()

    return True
