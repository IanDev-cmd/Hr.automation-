"""Ofsted timeline: any employment or education gap longer than 0 days."""

from typing import Any, Dict, List


def unexplained_gaps(history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return gap rows with days > 0 and no written explanation."""
    open_rows = []
    for row in history:
        if not row.get("gap"):
            continue
        days = int(row.get("days") or 0)
        if days <= 0:
            continue
        if str(row.get("explanation") or "").strip():
            continue
        open_rows.append(row)
    return open_rows
