"""Indeed import, Graph token shape, and home-manager scope."""

import base64
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient

from app.config import Settings
from app.db import connection, reset_db
from app.main import app
from app.services.ms_graph import MicrosoftGraphClient


def token(client, role, home=""):
    response = client.post(
        "/api/v1/auth/token",
        json={"username": "Kenny", "password": "desk", "role": role, "home_name": home},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def indeed_body(**overrides):
    body = {
        "full_name": "Ada Okonkwo",
        "email": "ada@example.com",
        "phone": "07000000001",
        "home_name": "Mayfield Lodge",
        "nvq_level_3": True,
        "driving_licence_one_year": True,
        "right_to_work": True,
        "years_experience": 3,
    }
    body.update(overrides)
    return body


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        reset_db("sqlite:///:memory:")
        self.client = TestClient(app)

    def test_indeed_webhook_stores_screening_and_routes_the_queue(self):
        passed = self.client.post("/api/v1/integrations/indeed/webhook", json=indeed_body())
        self.assertEqual(passed.status_code, 200, passed.text)
        self.assertEqual(passed.json()["stage"], "prescreen")
        candidate_id = passed.json()["candidate_id"]
        row = connection().execute(
            "SELECT * FROM screening_answers WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        self.assertEqual(row["nvq_level_3"], 1)
        self.assertEqual(row["driving_licence_one_year"], 1)
        self.assertEqual(row["right_to_work"], 1)
        self.assertEqual(row["years_experience"], 3)

        blocked = self.client.post(
            "/api/v1/integrations/indeed/webhook",
            json=indeed_body(full_name="Sam Hale", driving_licence_one_year=False, email="sam@example.com"),
        )
        self.assertEqual(blocked.status_code, 200, blocked.text)
        self.assertEqual(blocked.json()["stage"], "historic")
        self.assertIn("driving licence", blocked.json()["rejection_reason"])
        stored = connection().execute(
            "SELECT stage, rejection_reason, reapply_eligible_at FROM candidates WHERE id = ?",
            (blocked.json()["candidate_id"],),
        ).fetchone()
        self.assertEqual(stored["stage"], "historic")
        self.assertTrue(stored["reapply_eligible_at"])

    def test_graph_client_credentials_request(self):
        client = MicrosoftGraphClient(
            Settings(ms_tenant_id="sequel-tenant", ms_client_id="cid", ms_client_secret="sec")
        )
        request = client.client_credentials_request()
        self.assertEqual(request["method"], "POST")
        self.assertEqual(
            request["url"],
            "https://login.microsoftonline.com/sequel-tenant/oauth2/v2.0/token",
        )
        self.assertEqual(request["data"]["grant_type"], "client_credentials")
        self.assertEqual(request["data"]["scope"], "https://graph.microsoft.com/.default")
        self.assertEqual(request["data"]["client_id"], "cid")
        self.assertEqual(request["headers"]["Content-Type"], "application/x-www-form-urlencoded")

    def test_home_manager_cannot_open_another_homes_file(self):
        created = self.client.post("/api/v1/integrations/indeed/webhook", json=indeed_body())
        candidate_id = created.json()["candidate_id"]
        fernleigh = token(self.client, "HOME_MANAGER", "Fernleigh House")
        denied = self.client.get(f"/api/v1/hr/candidates/{candidate_id}", headers=fernleigh)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["detail"], "This home is outside your scope")

        admin = token(self.client, "HR_ADMIN")
        allowed = self.client.get(f"/api/v1/hr/candidates/{candidate_id}", headers=admin)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["home_name"], "Mayfield Lodge")
        self.assertTrue(allowed.json()["screening"]["nvq_level_3"])

        mayfield = token(self.client, "HOME_MANAGER", "Mayfield Lodge")
        own = self.client.get(f"/api/v1/hr/candidates/{candidate_id}", headers=mayfield)
        self.assertEqual(own.status_code, 200)

    def test_signature_certificate_keeps_the_token_as_a_hash(self):
        secret = "email-auth-token-9f3a"
        admin = token(self.client, "HR_ADMIN")
        response = self.client.post(
            "/api/v1/hr/signatures/execute",
            headers={**admin, "User-Agent": "SequelDesk/1", "X-Forwarded-For": "203.0.113.8"},
            json={
                "candidate_id": "joe",
                "full_name": "Joe Bloggs",
                "home_name": "Mayfield Lodge",
                "signer_email": "joe.bloggs@example.com",
                "email_token": secret,
                "document_text": "Conditional offer of employment",
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertNotIn(secret, response.text)
        self.assertEqual(body["audit"]["ip_address"], "203.0.113.8")
        self.assertEqual(len(body["audit"]["document_sha256"]), 64)
        pdf = base64.b64decode(body["pdf_base64"])
        self.assertTrue(pdf.startswith(b"%PDF"))
        self.assertIn(body["audit"]["document_sha256"].encode(), pdf)
        self.assertNotIn(secret.encode(), pdf)


if __name__ == "__main__":
    unittest.main()
