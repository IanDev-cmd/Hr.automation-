"""Outbound webhooks for the Google Apps Script desk."""

import logging

import httpx

from app.config import Settings

logger = logging.getLogger("hr.apps_script")

_SECRET_KEYS = {"account_number", "account", "sort_code", "token"}


class AppsScriptClient:
    """Post a named action to Apps Script, or simulate one when no URL is set."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout = 15.0

    def dispatch(self, action: str, payload: dict) -> dict:
        safe = {key: value for key, value in payload.items() if key not in _SECRET_KEYS}
        url = (self.settings.apps_script_webhook_url or "").strip()
        if not url:
            logger.warning("APPS_SCRIPT_WEBHOOK_URL is empty; simulating %s", action)
            return {"status": "SIMULATED", "action": action}

        body = {**safe, "action": action, "token": self.settings.hr_webhook_token}
        try:
            response = httpx.post(url, json=body, timeout=self.timeout)
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error("Apps Script timed out for %s", action)
            return {"status": "ERROR", "detail": "Apps Script timed out"}
        except httpx.HTTPError as exc:
            logger.error("Apps Script connection failed for %s: %s", action, exc)
            return {"status": "ERROR", "detail": "Apps Script unavailable"}

        try:
            data = response.json()
        except ValueError:
            logger.error("Apps Script returned a non-JSON body for %s", action)
            return {"status": "ERROR", "detail": "Apps Script returned an unreadable body"}
        if isinstance(data, dict):
            return data
        return {"status": "OK", "action": action}
