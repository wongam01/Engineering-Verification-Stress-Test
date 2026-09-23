import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.application.role_grounding import (
    ground_semantic_candidates,
    semantic_candidate_grounding_eligibility,
)


def valid_review_candidate():
    extraction = {
        "source_line_id": "L1",
        "constraint_id": "UNSPECIFIED",
        "type": "range",
        "unit": "HRC",
        "variable": "Tip hardness",
        "min": "50",
        "max": "57",
        "left": None,
        "right": None,
        "variables": [],
        "limit": None,
        "needs_review": True,
        "review_reason": (
            "Constraint ID is not explicitly provided."
        ),
        "constraint_role": "requirement",
        "source_name": "source.pdf",
        "source_text": (
            "Tip hardness spec changed to 50-57 HRC."
        ),
    }

    return SimpleNamespace(
        candidate_id="review-required",
        role="requirement",
        source_name="source.pdf",
        source_text=extraction["source_text"],
        extraction=extraction,
        adapter_accepted=False,
    )


class RoleGroundingEligibilityTest(unittest.TestCase):
    def test_review_required_structure_can_enter_grounding(self):
        candidate = valid_review_candidate()

        eligible, reason = (
            semantic_candidate_grounding_eligibility(
                candidate
            )
        )

        self.assertTrue(eligible)
        self.assertEqual(reason, "")

    def test_unsupported_candidate_is_blocked(self):
        candidate = valid_review_candidate()
        candidate.extraction["type"] = "unsupported"

        eligible, reason = (
            semantic_candidate_grounding_eligibility(
                candidate
            )
        )

        self.assertFalse(eligible)
        self.assertIn(
            "unsupported",
            reason.lower(),
        )

    def test_review_required_candidate_reaches_evaluator(self):
        candidate = valid_review_candidate()
        analysis = SimpleNamespace(
            candidates=[candidate]
        )

        grounded = SimpleNamespace(
            status="SUPPORTED",
        )

        with patch(
            "src.application.role_grounding."
            "evaluate_candidate_role_grounding",
            return_value=grounded,
        ) as evaluator:
            result = ground_semantic_candidates(
                analysis,
                max_workers=1,
            )

        evaluator.assert_called_once()
        self.assertIs(
            result[candidate.candidate_id],
            grounded,
        )


if __name__ == "__main__":
    unittest.main()
