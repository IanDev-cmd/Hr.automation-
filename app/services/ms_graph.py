"""Microsoft Graph calls for Teams, Outlook, and SharePoint."""

import logging
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger("hr.graph")

GRAPH = "https://graph.microsoft.com/v1.0"
HOME_FOLDERS = {
    "Mayfield Lodge": "Mayfield",
    "Rainbow Lodge": "Rainbow",
    "Fernleigh House": "Fernleigh",
}


class MicrosoftGraphClient:
    """Build Graph requests. An empty client id stays in simulation."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.timeout = 15.0

    def client_credentials_request(self) -> dict[str, Any]:
        tenant = (self.settings.ms_tenant_id or "common").strip() or "common"
        return {
            "method": "POST",
            "url": f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            "data": {
                "client_id": self.settings.ms_client_id,
                "client_secret": self.settings.ms_client_secret,
                "scope": "https://graph.microsoft.com/.default",
                "grant_type": "client_credentials",
            },
            "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        }

    def fetch_token(self) -> dict[str, Any]:
        request = self.client_credentials_request()
        if not (self.settings.ms_client_id and self.settings.ms_client_secret):
            logger.warning("Microsoft Graph client credentials are empty; simulating a token")
            safe = {key: value for key, value in request["data"].items() if key != "client_secret"}
            return {
                "status": "SIMULATED",
                "token_type": "Bearer",
                "access_token": "simulated",
                "request": {"method": request["method"], "url": request["url"], "data": safe},
            }
        try:
            response = httpx.post(request["url"], data=request["data"], headers=request["headers"], timeout=self.timeout)
            response.raise_for_status()
        except httpx.TimeoutException:
            logger.error("Microsoft token request timed out")
            return {"status": "ERROR", "detail": "Microsoft token request timed out", "request": request}
        except httpx.HTTPError as exc:
            logger.error("Microsoft token request failed: %s", exc)
            return {"status": "ERROR", "detail": "Microsoft token request failed", "request": request}
        body = response.json()
        body["request"] = {"url": request["url"], "grant_type": request["data"]["grant_type"]}
        return body

    def _auth_header(self) -> dict[str, str]:
        token = self.fetch_token()
        access = token.get("access_token") or "simulated"
        return {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}

    def create_online_meeting(self, subject: str, start: str, end: str, attendees: list[str]) -> dict[str, Any]:
        path = "/me/onlineMeetings"
        body = {
            "subject": subject,
            "startDateTime": start,
            "endDateTime": end,
            "participants": {"attendees": [{"upn": email, "role": "attendee"} for email in attendees]},
        }
        return self._call("POST", path, body)

    def attach_recording(self, meeting_id: str, recording_name: str, transcript_text: str) -> dict[str, Any]:
        path = f"/me/onlineMeetings/{meeting_id}/recordings"
        body = {"name": recording_name, "transcript": transcript_text}
        return self._call("POST", path, body)

    def upload_sharepoint(self, home_name: str, candidate_name: str, file_name: str, content: bytes) -> dict[str, Any]:
        folder = HOME_FOLDERS.get(home_name, "Mayfield")
        path = f"/sites/root/drive/root:/{folder}/{candidate_name}/{file_name}:/content"
        planned = {"method": "PUT", "url": GRAPH + path, "bytes": len(content), "home_folder": folder}
        if not self.settings.ms_client_id:
            logger.warning("SharePoint upload simulated for %s/%s", folder, file_name)
            return {"status": "SIMULATED", "request": planned}
        return {"status": "QUEUED", "request": planned}

    def send_mail(self, to: str, subject: str, body: str) -> dict[str, Any]:
        payload = {
            "message": {
                "subject": subject,
                "body": {"contentType": "Text", "content": body},
                "toRecipients": [{"emailAddress": {"address": to}}],
            }
        }
        return self._call("POST", "/me/sendMail", payload)

    def create_event(self, subject: str, start: str, end: str, attendees: list[str]) -> dict[str, Any]:
        body = {
            "subject": subject,
            "start": {"dateTime": start, "timeZone": "Europe/London"},
            "end": {"dateTime": end, "timeZone": "Europe/London"},
            "attendees": [{"emailAddress": {"address": email}, "type": "required"} for email in attendees],
        }
        return self._call("POST", "/me/events", body)

    def _call(self, method: str, path: str, body: dict) -> dict[str, Any]:
        request = {"method": method, "url": GRAPH + path, "json": body, "headers": self._auth_header()}
        if not self.settings.ms_client_id:
            logger.warning("Microsoft Graph %s %s simulated", method, path)
            return {"status": "SIMULATED", "request": request}
        try:
            response = httpx.request(method, request["url"], json=body, headers=request["headers"], timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Microsoft Graph %s failed: %s", path, exc)
            return {"status": "ERROR", "detail": "Microsoft Graph call failed", "request": {"url": request["url"]}}
        if response.content:
            try:
                return {"status": "OK", "body": response.json()}
            except ValueError:
                return {"status": "OK"}
        return {"status": "OK"}
