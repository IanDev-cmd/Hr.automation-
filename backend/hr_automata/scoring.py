"""Dual-interviewer consensus for the 28 Support Worker scenarios."""

from typing import Any, Dict

# Safeguarding scenarios inside the 28-question panel.
# These ids are mirrored in index.html (SAFEGUARDING_IDS).
SAFEGUARDING_QUESTION_IDS = frozenset({3, 7, 11, 14, 18, 21, 24, 27})


class InterviewScoringAggregator:
    """Aggregate two panel score sheets and flag safeguarding disagreements.

    A question scores 0–5. A gap above 2 points on a safeguarding question,
    or a total gap above 10, holds the offer until the panel agrees.
    """

    SAFEGUARDING_QUESTION_IDS = SAFEGUARDING_QUESTION_IDS

    def evaluate_panel_scores(
        self, interviewer_1_scores: Dict[int, int], interviewer_2_scores: Dict[int, int]
    ) -> Dict[str, Any]:
        self._check_range(interviewer_1_scores)
        self._check_range(interviewer_2_scores)

        discrepancies = []
        total_score_1 = sum(interviewer_1_scores.values())
        total_score_2 = sum(interviewer_2_scores.values())

        for q_id in range(1, 29):
            s1 = interviewer_1_scores.get(q_id, 0)
            s2 = interviewer_2_scores.get(q_id, 0)
            diff = abs(s1 - s2)
            if diff > 2:
                discrepancies.append(
                    {
                        "question_id": q_id,
                        "is_safeguarding": q_id in self.SAFEGUARDING_QUESTION_IDS,
                        "score_interviewer_1": s1,
                        "score_interviewer_2": s2,
                        "difference": diff,
                    }
                )

        requires_consensus_discussion = any(
            item["is_safeguarding"] for item in discrepancies
        ) or abs(total_score_1 - total_score_2) > 10

        return {
            "interviewer_1_total": total_score_1,
            "interviewer_2_total": total_score_2,
            "average_score": round((total_score_1 + total_score_2) / 2, 2),
            "discrepancies_found": discrepancies,
            "requires_consensus_discussion": requires_consensus_discussion,
            "can_proceed_to_offer": not requires_consensus_discussion,
        }

    @staticmethod
    def _check_range(scores: Dict[int, int]) -> None:
        for q_id, score in scores.items():
            if not isinstance(score, int) or isinstance(score, bool):
                raise TypeError(f"question {q_id} score must be an integer")
            if score < 0 or score > 5:
                raise ValueError(f"question {q_id} score must be from 0 to 5")
