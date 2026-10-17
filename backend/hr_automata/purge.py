"""GDPR retention: rejected files leave after 180 days unless watchlisted."""

import datetime
from typing import Any, Dict, List


class GDPRDataPurgeWorker:
    """List rejected candidates due for purge. Watchlist names are kept."""

    def identify_purgeable_records(self, db_records: List[Dict[str, Any]]) -> List[str]:
        purge_ids = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for record in db_records:
            if record.get("overall_status") != "REJECTED":
                continue
            if record.get("is_on_reapply_watchlist"):
                continue
            rejected_raw = record.get("rejected_at")
            candidate_id = record.get("candidate_id")
            if not rejected_raw or not candidate_id:
                continue
            rejected_date = self._as_utc(rejected_raw)
            days_elapsed = (now - rejected_date).days
            if days_elapsed >= 180:
                purge_ids.append(candidate_id)

        return purge_ids

    @staticmethod
    def _as_utc(value: Any) -> datetime.datetime:
        if isinstance(value, str):
            value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not isinstance(value, datetime.datetime):
            raise TypeError("rejected_at must be an ISO timestamp")
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc)
