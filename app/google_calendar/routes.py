import json
import secrets
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from .service import get_upcoming_events, get_busy_periods
from app.services.study_scheduler import find_available_slots

from app.google_calendar.oauth import (
    create_oauth_flow,
    credentials_to_dict,
)

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
TOKEN_FILE = BASE_DIR / "token.json"


@router.get("/auth/google")
def connect_google_calendar(request: Request):
    """Start Google OAuth authentication."""

    flow = create_oauth_flow()

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )

    # Save OAuth state and PKCE verifier for the callback.
    request.session["google_oauth_state"] = state
    request.session["google_code_verifier"] = flow.code_verifier

    return RedirectResponse(
        url=authorization_url,
        status_code=302,
    )


@router.get("/auth/google/callback")
def google_callback(request: Request):
    """Handle Google's OAuth callback."""

    saved_state = request.session.get("google_oauth_state")
    returned_state = request.query_params.get("state")
    code_verifier = request.session.get("google_code_verifier")

    # Validate the OAuth state.
    if not saved_state or saved_state != returned_state:
        raise HTTPException(
            status_code=400,
            detail="Invalid or missing OAuth state. Please reconnect.",
        )

    # PKCE requires the original code verifier.
    if not code_verifier:
        raise HTTPException(
            status_code=400,
            detail="Missing PKCE code verifier. Please reconnect.",
        )

    flow = create_oauth_flow()
    flow.state = saved_state
    flow.code_verifier = code_verifier

    # Exchange the authorization code for credentials.
    flow.fetch_token(
        authorization_response=str(request.url)
    )

    credentials = flow.credentials

    # Save credentials for local single-user testing.
    TOKEN_FILE.write_text(
        json.dumps(credentials_to_dict(credentials)),
        encoding="utf-8",
    )

    # Remove temporary OAuth session values.
    request.session.pop("google_oauth_state", None)
    request.session.pop("google_code_verifier", None)

    return RedirectResponse(
        url="/?google_connected=1",
        status_code=303,
    )


@router.get("/auth/google/status")
def google_connection_status():
    """Check whether Google Calendar credentials exist."""

    return {
        "connected": TOKEN_FILE.exists()
    }


@router.post("/auth/google/disconnect")
def disconnect_google_calendar():
    """Remove locally stored Google credentials."""

    TOKEN_FILE.unlink(missing_ok=True)

    return RedirectResponse(
        url="/",
        status_code=303,
    )

@router.get("/auth/google/events")
def google_calendar_events():
    """Return upcoming Google Calendar events."""

    try:
        events = get_upcoming_events(days=7)

        return {
            "connected": True,
            "count": len(events),
            "events": events,
        }

    except Exception:
        # Avoid exposing internal authentication details.
        raise HTTPException(
            status_code=502,
            detail="Unable to retrieve Google Calendar events.",
        )

@router.get("/auth/google/busy")
def google_busy():
    """Return busy periods from connected calendars."""

    try:
        busy_periods = get_busy_periods(days=7)

        return {
            "connected": True,
            "count": len(busy_periods),
            "busy_periods": busy_periods,
        }

    except FileNotFoundError:
        return {
            "connected": False,
            "count": 0,
            "busy_periods": [],
        }

@router.get("/auth/google/available")
def google_available():
    """Return available study slots from Google Calendar."""

    # Retrieve existing calendar commitments.
    busy_periods = get_busy_periods(days=7)

    # Calculate available study times.
    available_slots = find_available_slots(
        busy_periods,
        days=7,
    )

    return {
        "connected": True,
        "count": len(available_slots),
        "available_slots": available_slots,
    }