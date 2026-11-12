
from app.services.auth_service import (
    hash_password,
    verify_password,
)


def test_password_is_hashed():
    """Verify passwords are not stored as plain text."""
    password = "SecurePassword123!"

    hashed = hash_password(password)

    assert hashed != password
    assert hashed.startswith("$argon2")


def test_correct_password():
    """Verify the correct password is accepted."""
    password = "SecurePassword123!"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_incorrect_password():
    """Verify an incorrect password is rejected."""
    hashed = hash_password("SecurePassword123!")

    assert verify_password("WrongPassword123!", hashed) is False


def test_invalid_password_hash():
    """Verify invalid hashes are rejected safely."""
    assert verify_password(
        "SecurePassword123!",
        "invalid_hash"
    ) is False


def test_unique_password_hashes():
    """Verify Argon2 generates salted password hashes."""
    password = "SecurePassword123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(password, first_hash)
    assert verify_password(password, second_hash)