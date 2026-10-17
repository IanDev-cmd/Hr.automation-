"""API checks for pay, panel scores, and masked payroll handoff."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient

from app.main import app
from app.services.payroll import clear_handoffs


def panel(score=4):
    return {str(question): score for question in range(1, 29)}


class ApiTests(unittest.TestCase):
    def setUp(self):
        clear_handoffs()
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_sleep_in_rates_follow_the_home(self):
        bournemouth = self.client.post(
            "/api/v1/hr/pay/calculate",
            json={"home_name": "Mayfield Lodge", "expected_sleep_ins_per_week": 2, "employment_type": "Full-time"},
        )
        cornwall = self.client.post(
            "/api/v1/hr/pay/calculate",
            json={"home_name": "Fernleigh House", "expected_sleep_ins_per_week": 2, "employment_type": "Full-time"},
        )
        self.assertEqual(bournemouth.status_code, 200)
        self.assertEqual(cornwall.status_code, 200)
        self.assertEqual(bournemouth.json()["sleep_in_rate_per_night"], 63.0)
        self.assertEqual(bournemouth.json()["region"], "Bournemouth")
        self.assertEqual(bournemouth.json()["total_gross_annual_package"], 33852.0)
        self.assertEqual(cornwall.json()["sleep_in_rate_per_night"], 60.0)
        self.assertEqual(cornwall.json()["region"], "Cornwall")
        self.assertEqual(cornwall.json()["total_gross_annual_package"], 33540.0)

    def test_safeguarding_discrepancy_holds_the_offer(self):
        second = panel()
        second["3"] = 1
        response = self.client.post(
            "/api/v1/hr/interviews/evaluate",
            json={"interviewer_1_scores": panel(), "interviewer_2_scores": second},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["requires_consensus_discussion"])
        self.assertFalse(body["can_proceed_to_offer"])
        flagged = body["discrepancies_found"][0]
        self.assertEqual(flagged["question_id"], 3)
        self.assertTrue(flagged["is_safeguarding"])

    def test_score_outside_the_scale_is_rejected(self):
        response = self.client.post(
            "/api/v1/hr/interviews/evaluate",
            json={"interviewer_1_scores": {"1": 9}, "interviewer_2_scores": {"1": 4}},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "ERROR")

    def test_payroll_handoff_keeps_only_the_last_four(self):
        account = "12345678"
        response = self.client.post(
            "/api/v1/hr/payroll/handoff",
            json={
                "candidate_id": "joe",
                "candidate_name": "Joe Bloggs",
                "home_name": "Mayfield Lodge",
                "sort_code": "20-00-00",
                "account_number": account,
                "p45_received": True,
                "starter_declaration": True,
                "emergency_name": "Pat Bloggs",
                "emergency_phone": "07000000000",
                "job_description_signed": True,
                "working_time_opt_out": False,
                "key_phone_signed": True,
            },
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["account_last4"], "5678")
        self.assertEqual(body["storage"]["account_last4"], "5678")
        self.assertTrue(body["storage"]["bank_submitted"])
        self.assertNotIn(account, response.text)
        self.assertNotIn("account_number", body["storage"])
        self.assertEqual(body["apps_script"]["status"], "SIMULATED")

        missing = self.client.get("/api/v1/hr/payroll/handoff/nobody")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["detail"], "Payroll handoff not found")

    def test_invalid_sort_code_is_rejected(self):
        response = self.client.post(
            "/api/v1/hr/payroll/handoff",
            json={"candidate_id": "joe", "sort_code": "20", "account_number": "12345678"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("12345678", response.text)


if __name__ == "__main__":
    unittest.main()
