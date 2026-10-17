"""Chase dates-only or missing references after three business days."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db import connection
from app.services.ms_graph import MicrosoftGraphClient

logger = logging.getLogger("hr.references")

TEMPLATE_NAME = "REFERENCE REQUEST - ADDITIONAL INFORMATION"
TEMPLATE_BODY = (
    "REFERENCE REQUEST - ADDITIONAL INFORMATION\n\n"
    "Children's Homes (England) Regulations 2015 require a reference that covers "
    "conduct, duties, and the reason for leaving. A reply that confirms dates only "
    "is not sufficient.\n\n"
    "Please send that additional information to Sequel Support HR."
)
_scheduler = None


def business_days_since(sent_at: datetime, now: datetime) -> int:
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    day = sent_at.date()
    end = now.date()
    count = 0
    while day < end:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count += 1
    return count


def chase_due_references(now: datetime | None = None) -> list[dict]:
    moment = now or datetime.now(timezone.utc)
    graph = MicrosoftGraphClient(get_settings())
    rows = connection().execute(
        "SELECT * FROM reference_requests WHERE received = 0"
    ).fetchall()
    sent = []
    for row in rows:
        sent_at = datetime.fromisoformat(row["sent_at"].replace("Z", "+00:00"))
        if business_days_since(sent_at, moment) < 3:
            continue
        already = connection().execute(
            "SELECT id FROM reference_chases WHERE reference_id = ?",
            (row["id"],),
        ).fetchone()
        if already:
            continue
        note = f"Chase to {row['referee_name']} for candidate {row['candidate_id']}"
        if row["referee_email"]:
            graph.send_mail(row["referee_email"], TEMPLATE_NAME, TEMPLATE_BODY)
        chase_id = "chs_" + uuid.uuid4().hex[:12]
        connection().execute(
            """
            INSERT INTO reference_chases (id, reference_id, chased_at, template_name, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chase_id, row["id"], moment.isoformat(), TEMPLATE_NAME, note),
        )
        sent.append({"id": chase_id, "reference_id": row["id"], "template_name": TEMPLATE_NAME, "note": note})
    connection().commit()
    if sent:
        logger.info("Reference chases sent: %s", len(sent))
    return sent


def register_request(candidate_id: str, referee_name: str, referee_email: str, sent_at: str, dates_only: bool) -> str:
    request_id = "ref_" + uuid.uuid4().hex[:12]
    connection().execute(
        """
        INSERT INTO reference_requests (id, candidate_id, referee_name, referee_email, sent_at, dates_only, received)
        VALUES (?, ?, ?, ?, ?, ?, 0)
        """,
        (request_id, candidate_id, referee_name, referee_email, sent_at, 1 if dates_only else 0),
    )
    connection().commit()
    return request_id


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        logger.warning("APScheduler is not installed; reference chasing stays on demand")
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(chase_due_references, "interval", hours=24, id="reference-chaser")
    _scheduler.start()
    logger.info("Reference chaser scheduled every 24 hours")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
