"""Continuous 90-day DBS Update Service re-check."""

import datetime
from typing import Optional, Union


def dbs_recheck_due(
    last_checked: Union[str, datetime.datetime],
    now: Optional[datetime.datetime] = None,
    interval_days: int = 90,
) -> bool:
    """True when the last Update Service check is interval_days old or older."""
    if isinstance(last_checked, str):
        last_checked = datetime.datetime.fromisoformat(last_checked.replace("Z", "+00:00"))
    if last_checked.tzinfo is None:
        last_checked = last_checked.replace(tzinfo=datetime.timezone.utc)
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)
    return (now - last_checked).days >= interval_days
