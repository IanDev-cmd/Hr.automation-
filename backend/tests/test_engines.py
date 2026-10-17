import datetime
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hr_automata.completion import vetting_completion
from hr_automata.dbs import dbs_recheck_due
from hr_automata.gaps import unexplained_gaps
from hr_automata.integrity import DocumentIntegrityEngine
from hr_automata.pay import PayAndAllowanceCalculator
from hr_automata.purge import GDPRDataPurgeWorker
from hr_automata.scoring import InterviewScoringAggregator


class ScoringTests(unittest.TestCase):
    def test_safeguarding_gap_holds_the_offer(self):
        panel = InterviewScoringAggregator()
        first = {q: 4 for q in range(1, 29)}
        second = dict(first)
        second[3] = 1
        result = panel.evaluate_panel_scores(first, second)
        self.assertTrue(result["requires_consensus_discussion"])
        self.assertFalse(result["can_proceed_to_offer"])
        self.assertEqual(result["discrepancies_found"][0]["question_id"], 3)
        self.assertTrue(result["discrepancies_found"][0]["is_safeguarding"])

    def test_matched_panel_can_proceed(self):
        panel = InterviewScoringAggregator()
        scores = {q: 4 for q in range(1, 29)}
        result = panel.evaluate_panel_scores(scores, dict(scores))
        self.assertEqual(result["average_score"], 112.0)
        self.assertTrue(result["can_proceed_to_offer"])
        self.assertEqual(result["discrepancies_found"], [])

    def test_score_out_of_range_is_rejected(self):
        panel = InterviewScoringAggregator()
        with self.assertRaises(ValueError):
            panel.evaluate_panel_scores({1: 6}, {1: 4})


class PayTests(unittest.TestCase):
    def test_bournemouth_package_matches_the_contract(self):
        package = PayAndAllowanceCalculator().calculate_offer_package("Mayfield Lodge", 2)
        self.assertEqual(package["sleep_in_rate_per_night"], 63.00)
        self.assertEqual(package["projected_sleep_ins_annual"], 104)
        self.assertEqual(package["total_gross_annual_package"], 33852.00)

    def test_cornwall_rate_is_lower(self):
        package = PayAndAllowanceCalculator().calculate_offer_package("Fernleigh House", 2)
        self.assertEqual(package["sleep_in_rate_per_night"], 60.00)
        self.assertEqual(package["region"], "Cornwall")
        self.assertEqual(package["total_gross_annual_package"], 33540.00)


class IntegrityAndRetentionTests(unittest.TestCase):
    def test_sha256_and_watermark(self):
        engine = DocumentIntegrityEngine()
        digest = engine.generate_sha256_checksum(b"")
        self.assertEqual(
            digest,
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )
        mark = engine.build_watermark_metadata("cand_8f91a20b", "Emily Carter", "2026-10-17")
        self.assertIn("cand_8f91a20b", mark["watermark_text"])
        self.assertEqual(mark["legal_status"], "COMPLIANT_UNDER_CHILDRENS_HOMES_REGS_2015")

    def test_purge_skips_watchlist_and_recent_rejects(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        old = (now - datetime.timedelta(days=200)).isoformat()
        recent = (now - datetime.timedelta(days=30)).isoformat()
        worker = GDPRDataPurgeWorker()
        ids = worker.identify_purgeable_records(
            [
                {"candidate_id": "old", "overall_status": "REJECTED", "is_on_reapply_watchlist": False, "rejected_at": old},
                {"candidate_id": "kept", "overall_status": "REJECTED", "is_on_reapply_watchlist": True, "rejected_at": old},
                {"candidate_id": "fresh", "overall_status": "REJECTED", "is_on_reapply_watchlist": False, "rejected_at": recent},
                {"candidate_id": "hired", "overall_status": "OFFERED", "is_on_reapply_watchlist": False, "rejected_at": old},
            ]
        )
        self.assertEqual(ids, ["old"])

    def test_gap_and_dbs_and_completion(self):
        gaps = unexplained_gaps(
            [
                {"gap": True, "days": 4, "explanation": "Moved house"},
                {"gap": True, "days": 73, "explanation": ""},
                {"gap": False, "days": 0, "explanation": ""},
            ]
        )
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["days"], 73)
        checked = datetime.datetime(2026, 6, 1, tzinfo=datetime.timezone.utc)
        today = datetime.datetime(2026, 10, 17, tzinfo=datetime.timezone.utc)
        self.assertTrue(dbs_recheck_due(checked, now=today))
        self.assertFalse(dbs_recheck_due(datetime.datetime(2026, 9, 1, tzinfo=datetime.timezone.utc), now=today))
        self.assertEqual(vetting_completion([True, True, False, False]), 50)


if __name__ == "__main__":
    unittest.main()
