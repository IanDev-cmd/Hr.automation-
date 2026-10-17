"""DBS Update Service polling stub and 90-day recheck alerts."""

import uuid
from datetime import datetime, timedelta, timezone

from hr_automata.dbs import dbs_recheck_due

from app.db import connection


class DbsVerifier:
    """Record a portal result and flag checks that are due or unverified."""

    def record(self, candidate_id: str, status: str, checked_at: str, certificate_number: str = "") -> dict:
        checked = datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
        if checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        due = dbs_recheck_due(checked)
        next_due = (checked + timedelta(days=90)).isoformat()
        check_id = "dbs_" + uuid.uuid4().hex[:12]
        connection().execute(
            """
            INSERT INTO dbs_checks (id, candidate_id, certificate_number, status, checked_at, next_due)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (check_id, candidate_id, certificate_number, status, checked.isoformat(), next_due),
        )
        connection().commit()
        alert = status.upper() != "CLEAR" or due
        return {
            "id": check_id,
            "candidate_id": candidate_id,
            "status": status,
            "checked_at": checked.isoformat(),
            "next_due": next_due,
            "recheck_due": due,
            "alert": alert,
        }

    def due_alerts(self) -> list[dict]:
        rows = connection().execute("SELECT * FROM dbs_checks").fetchall()
        alerts = []
        for row in rows:
            due = dbs_recheck_due(row["checked_at"])
            if due or row["status"].upper() != "CLEAR":
                alerts.append(
                    {
                        "id": row["id"],
                        "candidate_id": row["candidate_id"],
                        "status": row["status"],
                        "checked_at": row["checked_at"],
                        "recheck_due": due,
                    }
                )
        return alerts
