"""Discovery routes: Indeed, Graph, signatures, references, onboarding, and home scope."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.auth import DeskUser, assert_home, current_user, issue_token
from app.config import get_settings
from app.db import connection, home_id, home_name
from app.services.dbs_verifier import DbsVerifier
from app.services.indeed import import_application
from app.services.ms_graph import MicrosoftGraphClient
from app.services.signatures import execute_signature
from app.workers.reference_chaser import chase_due_references, register_request

router = APIRouter()
_dbs = DbsVerifier()
CLEARED = {"signoff", "induction", "cleared", "offered"}
COURSES = {"level3_diploma", "team_teach", "pace"}


def _graph() -> MicrosoftGraphClient:
    return MicrosoftGraphClient(get_settings())


def _ensure_candidate(candidate_id: str, full_name: str, email: str, home: str):
    existing = connection().execute("SELECT id FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if existing:
        return _candidate(candidate_id)
    resolved = home_name(home) or "Mayfield Lodge"
    connection().execute(
        """
        INSERT INTO candidates (id, full_name, email, phone, home_id, stage, applied_at, source)
        VALUES (?, ?, ?, '', ?, 'signoff', ?, 'desk')
        """,
        (candidate_id, full_name or candidate_id, email, home_id(resolved), datetime.now(timezone.utc).isoformat()),
    )
    connection().commit()
    return _candidate(candidate_id)


def _candidate(candidate_id: str):
    row = connection().execute(
        """
        SELECT c.*, h.name AS home_name
        FROM candidates c LEFT JOIN homes h ON h.id = c.home_id
        WHERE c.id = ?
        """,
        (candidate_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return row


def _guard(request: Request, home: str) -> DeskUser:
    user = current_user(request)
    assert_home(user, home)
    return user


@router.post("/api/v1/auth/token")
def auth_token(body: dict) -> dict:
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    role = str(body.get("role") or "HR_ADMIN")
    home = str(body.get("home_name") or "")
    if not username or not password.strip():
        raise HTTPException(status_code=400, detail="Enter a user name and password")
    if role not in {"HR_ADMIN", "HOME_MANAGER"}:
        raise HTTPException(status_code=400, detail="Role is not recognised")
    if role == "HOME_MANAGER":
        if home_name(home) is None:
            raise HTTPException(status_code=400, detail="A home manager needs a Sequel home")
        home = home_name(home) or home
    else:
        home = ""
    return {
        "access_token": issue_token(username, role, home),
        "token_type": "Bearer",
        "role": role,
        "home_name": home,
    }


@router.post("/api/v1/integrations/indeed/webhook")
def indeed_webhook(body: dict, request: Request) -> dict:
    expected = get_settings().indeed_webhook_token.strip()
    supplied = request.headers.get("x-indeed-token", "") or str(body.get("token") or "")
    if expected and supplied != expected:
        raise HTTPException(status_code=401, detail="Indeed token was rejected")
    try:
        result = import_application(body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "OK", **result}


@router.get("/api/v1/hr/candidates/historic")
def historic(request: Request) -> dict:
    user = current_user(request)
    rows = connection().execute(
        """
        SELECT c.*, h.name AS home_name
        FROM candidates c LEFT JOIN homes h ON h.id = c.home_id
        WHERE c.stage = 'historic'
        ORDER BY c.applied_at DESC
        """
    ).fetchall()
    people = []
    for row in rows:
        if user.role == "HOME_MANAGER" and row["home_name"] != user.home_name:
            continue
        people.append(
            {
                "id": row["id"],
                "full_name": row["full_name"],
                "home_name": row["home_name"],
                "rejection_reason": row["rejection_reason"],
                "reapply_eligible_at": row["reapply_eligible_at"],
                "skills_tags": [tag for tag in (row["skills_tags"] or "").split(",") if tag],
            }
        )
    return {"candidates": people}


@router.get("/api/v1/hr/candidates/{candidate_id}")
def read_candidate(candidate_id: str, request: Request) -> dict:
    row = _candidate(candidate_id)
    _guard(request, row["home_name"] or "")
    screen = connection().execute(
        "SELECT * FROM screening_answers WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    return {
        "id": row["id"],
        "full_name": row["full_name"],
        "email": row["email"],
        "home_name": row["home_name"],
        "stage": row["stage"],
        "rejection_reason": row["rejection_reason"] or "",
        "skills_tags": [tag for tag in (row["skills_tags"] or "").split(",") if tag],
        "screening": None
        if screen is None
        else {
            "nvq_level_3": bool(screen["nvq_level_3"]),
            "driving_licence_one_year": bool(screen["driving_licence_one_year"]),
            "right_to_work": bool(screen["right_to_work"]),
            "years_experience": screen["years_experience"],
        },
    }


@router.post("/api/v1/hr/candidates/{candidate_id}/reengage")
def reengage(candidate_id: str, request: Request) -> dict:
    row = _candidate(candidate_id)
    user = _guard(request, row["home_name"] or "")
    if row["stage"] != "historic":
        raise HTTPException(status_code=400, detail="Only a historic candidate can be re-engaged")
    now = datetime.now(timezone.utc).isoformat()
    note = f"{user.username} re-opened {row['full_name']} for {row['home_name']}"
    connection().execute(
        "UPDATE candidates SET stage = 'prescreen', on_reapply_watchlist = 0 WHERE id = ?",
        (candidate_id,),
    )
    connection().execute(
        "INSERT INTO reengagement_alerts (id, candidate_id, note, created_at) VALUES (?, ?, ?, ?)",
        ("rea_" + uuid.uuid4().hex[:12], candidate_id, note, now),
    )
    connection().commit()
    return {"status": "OK", "candidate_id": candidate_id, "stage": "prescreen", "alert": note}


@router.post("/api/v1/hr/candidates/prerequisite-change")
def prerequisite_change(body: dict, request: Request) -> dict:
    user = current_user(request)
    if user.role != "HR_ADMIN":
        raise HTTPException(status_code=403, detail="Only HR admin can change hiring prerequisites")
    needle = str(body.get("matches") or "").strip().lower()
    note = str(body.get("note") or "").strip()
    if not needle or not note:
        raise HTTPException(status_code=400, detail="Say which rejection reason changed")
    rows = connection().execute(
        "SELECT id, full_name, rejection_reason FROM candidates WHERE stage = 'historic'"
    ).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    alerts = []
    for row in rows:
        if needle not in (row["rejection_reason"] or "").lower():
            continue
        alert_id = "rea_" + uuid.uuid4().hex[:12]
        text = f"{row['full_name']}: {note}"
        connection().execute(
            "INSERT INTO reengagement_alerts (id, candidate_id, note, created_at) VALUES (?, ?, ?, ?)",
            (alert_id, row["id"], text, now),
        )
        alerts.append({"id": alert_id, "candidate_id": row["id"], "note": text})
    connection().commit()
    return {"status": "OK", "alerts": alerts}


@router.post("/api/v1/hr/signatures/execute")
def sign(body: dict, request: Request) -> dict:
    candidate_id = str(body.get("candidate_id") or "")
    signer_email = str(body.get("signer_email") or "")
    email_token = str(body.get("email_token") or "")
    document_text = str(body.get("document_text") or "")
    if not candidate_id or "@" not in signer_email or not email_token or not document_text.strip():
        raise HTTPException(status_code=400, detail="Signer email, token, and document are required")
    row = _ensure_candidate(candidate_id, str(body.get("full_name") or ""), signer_email, str(body.get("home_name") or ""))
    _guard(request, row["home_name"] or "")
    forwarded = request.headers.get("x-forwarded-for", "")
    ip_address = forwarded.split(",")[0].strip() or (request.client.host if request.client else "")
    audit = execute_signature(
        candidate_id,
        signer_email,
        email_token,
        document_text,
        ip_address or "unknown",
        request.headers.get("user-agent", ""),
    )
    return {"status": "OK", "audit": {key: value for key, value in audit.items() if key != "pdf_base64"}, "pdf_base64": audit["pdf_base64"]}


@router.post("/api/v1/hr/references/chase")
def chase(body: dict, request: Request) -> dict:
    candidate_id = str(body.get("candidate_id") or "")
    row = _ensure_candidate(
        candidate_id,
        str(body.get("full_name") or ""),
        "",
        str(body.get("home_name") or ""),
    )
    _guard(request, row["home_name"] or "")
    referee = str(body.get("referee_name") or "").strip()
    if not referee:
        raise HTTPException(status_code=400, detail="Referee name is required")
    sent_at = str(body.get("sent_at") or datetime.now(timezone.utc).isoformat())
    request_id = register_request(
        candidate_id,
        referee,
        str(body.get("referee_email") or ""),
        sent_at,
        bool(body.get("dates_only", True)),
    )
    chased = chase_due_references()
    mine = [item for item in chased if item["reference_id"] == request_id]
    return {"status": "OK", "reference_id": request_id, "chased": bool(mine), "chases": mine}


@router.post("/api/v1/hr/onboarding/home-visit")
def home_visit(body: dict, request: Request) -> dict:
    row = _candidate(str(body.get("candidate_id") or ""))
    home = home_name(str(body.get("home_name") or row["home_name"] or ""))
    if home is None:
        raise HTTPException(status_code=400, detail="Home is not one of the Sequel houses")
    _guard(request, home)
    if row["stage"] not in CLEARED:
        raise HTTPException(status_code=400, detail="Book a home visit after clearance")
    visit_at = str(body.get("visit_at") or "")
    visitor = str(body.get("visitor_name") or "").strip()
    if not visit_at or not visitor:
        raise HTTPException(status_code=400, detail="Visit time and visitor are required")
    visit_id = "vis_" + uuid.uuid4().hex[:12]
    connection().execute(
        "INSERT INTO home_visits (id, candidate_id, home_id, visit_at, visitor_name) VALUES (?, ?, ?, ?, ?)",
        (visit_id, row["id"], home_id(home), visit_at, visitor),
    )
    connection().commit()
    mail = _graph().create_event(
        f"Home orientation · {row['full_name']}",
        visit_at,
        visit_at,
        [row["email"]] if row["email"] else [],
    )
    return {"status": "OK", "id": visit_id, "home_name": home, "calendar": mail["status"]}


@router.post("/api/v1/hr/training/book")
def book_training(body: dict, request: Request) -> dict:
    row = _candidate(str(body.get("candidate_id") or ""))
    _guard(request, row["home_name"] or "")
    if row["stage"] not in CLEARED:
        raise HTTPException(status_code=400, detail="Book training after clearance")
    course = str(body.get("course") or "")
    if course not in COURSES:
        raise HTTPException(status_code=400, detail="Course must be Level 3, Team Teach, or PACE")
    booked_for = str(body.get("booked_for") or "")
    if not booked_for:
        raise HTTPException(status_code=400, detail="A course date is required")
    booking_id = "trn_" + uuid.uuid4().hex[:12]
    connection().execute(
        "INSERT INTO training_bookings (id, candidate_id, course, booked_for) VALUES (?, ?, ?, ?)",
        (booking_id, row["id"], course, booked_for),
    )
    connection().commit()
    return {"status": "OK", "id": booking_id, "course": course, "booked_for": booked_for}


@router.post("/api/v1/integrations/dbs/webhook")
def dbs_webhook(body: dict) -> dict:
    candidate_id = str(body.get("candidate_id") or "")
    _candidate(candidate_id)
    status = str(body.get("status") or "UNVERIFIED")
    checked_at = str(body.get("checked_at") or datetime.now(timezone.utc).isoformat())
    try:
        result = _dbs.record(candidate_id, status, checked_at, str(body.get("certificate_number") or ""))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="checked_at must be an ISO date") from exc
    return {"status": "OK", **result}


@router.get("/api/v1/hr/dbs/alerts")
def dbs_alerts(request: Request) -> dict:
    current_user(request)
    return {"alerts": _dbs.due_alerts()}


@router.post("/api/v1/hr/interviews/teams")
def teams_meeting(body: dict, request: Request) -> dict:
    row = _candidate(str(body.get("candidate_id") or ""))
    _guard(request, row["home_name"] or "")
    attendees = [str(item) for item in body.get("attendees") or [] if item]
    if row["email"]:
        attendees.append(row["email"])
    if len(attendees) < 2:
        raise HTTPException(status_code=400, detail="A Teams interview needs the panel and the candidate")
    start = str(body.get("start") or "")
    end = str(body.get("end") or "")
    if not start or not end:
        raise HTTPException(status_code=400, detail="Start and end are required")
    subject = str(body.get("subject") or f"Interview · {row['full_name']}")
    meeting = _graph().create_online_meeting(subject, start, end, attendees)
    interview_id = "met_" + uuid.uuid4().hex[:12]
    join_url = ""
    if meeting.get("status") == "OK":
        join_url = (meeting.get("body") or {}).get("joinWebUrl") or ""
    connection().execute(
        "INSERT INTO interviews (id, candidate_id, subject, join_url) VALUES (?, ?, ?, ?)",
        (interview_id, row["id"], subject, join_url or "simulated"),
    )
    connection().commit()
    return {"status": "OK", "id": interview_id, "graph": meeting["status"], "join_url": join_url or "simulated"}


@router.post("/api/v1/hr/interviews/{interview_id}/recording")
def teams_recording(interview_id: str, body: dict, request: Request) -> dict:
    row = connection().execute("SELECT * FROM interviews WHERE id = ?", (interview_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Interview not found")
    candidate = _candidate(row["candidate_id"])
    _guard(request, candidate["home_name"] or "")
    name = str(body.get("recording_name") or "").strip()
    transcript = str(body.get("transcript_text") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Recording name is required")
    connection().execute(
        "UPDATE interviews SET recording_name = ?, transcript_text = ? WHERE id = ?",
        (name, transcript, interview_id),
    )
    connection().commit()
    attached = _graph().attach_recording(interview_id, name, transcript)
    return {"status": "OK", "id": interview_id, "graph": attached["status"], "recording_name": name}
