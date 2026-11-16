from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.services.auth_dependencies import require_user
from app.services.study_scheduler import find_available_slots
from app.google_calendar.credential_storage import (
    save_user_credentials, get_user_credentials, delete_user_credentials,
)
from app.google_calendar.oauth import create_oauth_flow, credentials_to_dict
from app.google_calendar.service import (
    CalendarNotConnected, get_upcoming_events, get_busy_periods,
)

router = APIRouter()


@router.get("/auth/google/login")
def connect_google_calendar(request: Request, current_user: User = Depends(require_user)):
    """Start OAuth for the logged-in student."""
    flow = create_oauth_flow()
    url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent",
    )
    request.session["google_oauth_state"] = state
    request.session["google_code_verifier"] = flow.code_verifier
    request.session["google_oauth_user_id"] = current_user.id
    return RedirectResponse(url=url, status_code=302)


@router.get("/auth/google/callback")
def google_callback(request: Request, db: Session = Depends(get_db),
                    current_user: User = Depends(require_user)):
    """Verify OAuth state, PKCE and student identity before storing tokens."""
    state = request.session.get("google_oauth_state")
    verifier = request.session.get("google_code_verifier")
    if not state or state != request.query_params.get("state"):
        raise HTTPException(status_code=400, detail="Invalid OAuth state. Reconnect Google Calendar.")
    if not verifier:
        raise HTTPException(status_code=400, detail="Missing PKCE verifier. Reconnect Google Calendar.")
    if request.session.get("google_oauth_user_id") != current_user.id:
        raise HTTPException(status_code=403, detail="OAuth flow belongs to another student.")
    flow = create_oauth_flow()
    flow.state = state
    flow.code_verifier = verifier
    flow.fetch_token(authorization_response=str(request.url))
    save_user_credentials(db, current_user.id, credentials_to_dict(flow.credentials))
    for key in ("google_oauth_state", "google_code_verifier", "google_oauth_user_id"):
        request.session.pop(key, None)
    return RedirectResponse(url="/?google_connected=1", status_code=303)


@router.get("/auth/google/status")
def google_connection_status(db: Session = Depends(get_db),
                             current_user: User = Depends(require_user)):
    return {"connected": get_user_credentials(db, current_user.id) is not None}


@router.post("/auth/google/disconnect")
def disconnect_google_calendar(db: Session = Depends(get_db),
                               current_user: User = Depends(require_user)):
    delete_user_credentials(db, current_user.id)
    return RedirectResponse(url="/", status_code=303)


@router.get("/auth/google/events")
def google_calendar_events(db: Session = Depends(get_db),
                           current_user: User = Depends(require_user)):
    try:
        events = get_upcoming_events(db, current_user.id, days=7)
    except CalendarNotConnected as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve Google Calendar events.") from exc
    return {"connected": True, "count": len(events), "events": events}


@router.get("/auth/google/busy")
def google_busy(db: Session = Depends(get_db),
                current_user: User = Depends(require_user)):
    try:
        busy = get_busy_periods(db, current_user.id, days=7)
    except CalendarNotConnected:
        return {"connected": False, "count": 0, "busy_periods": []}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve calendar availability.") from exc
    return {"connected": True, "count": len(busy), "busy_periods": busy}


@router.get("/auth/google/available")
def google_available(db: Session = Depends(get_db),
                     current_user: User = Depends(require_user)):
    try:
        busy = get_busy_periods(db, current_user.id, days=7)
    except CalendarNotConnected:
        return {"connected": False, "count": 0, "available_slots": []}
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Unable to retrieve calendar availability.") from exc
    slots = find_available_slots(busy, days=7)
    return {"connected": True, "count": len(slots), "available_slots": slots}
