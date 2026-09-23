import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.application.role_grounding import (
    ground_semantic_candidates,
)


class RoleGroundingPreGateTest(unittest.TestCase):
    def test_adapter_rejected_candidate_skips_ai(self):
        analysis = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    candidate_id="blocked",
                    role="requirement",
                    source_text="text",
                    source_name="source.pdf",
                    adapter_accepted=False,
                    source_location_ready=True,
                ),
            ]
        )

        with patch(
            "src.application.role_grounding."
            "evaluate_candidate_role_grounding"
        ) as evaluator:
            result = ground_semantic_candidates(
                analysis,
                max_workers=4,
            )

        evaluator.assert_not_called()

        self.assertEqual(
            result["blocked"].status,
            "REVIEW_REQUIRED",
        )
        self.assertEqual(
            result["blocked"].basis_type,
            "ADAPTER_REJECTED",
        )

    def test_unresolved_source_candidate_still_allows_role_grounding(self):
        analysis = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    candidate_id="unresolved",
                    role="verification",
                    source_text="text",
                    source_name="source.pdf",
                    adapter_accepted=True,
                    source_location_ready=False,
                ),
            ]
        )

        grounded = SimpleNamespace(
            status="SUPPORTED",
            basis_type="TEST",
        )

        with patch(
            "src.application.role_grounding."
            "evaluate_candidate_role_grounding",
            return_value=grounded,
        ) as evaluator:
            result = ground_semantic_candidates(
                analysis,
                max_workers=4,
            )

        self.assertEqual(
            evaluator.call_count,
            1,
        )

        self.assertIs(
            result["unresolved"],
            grounded,
        )

    def test_only_eligible_candidates_call_ai(self):
        candidates = [
            SimpleNamespace(
                candidate_id="blocked",
                role="requirement",
                source_text="A",
                source_name="a.pdf",
                adapter_accepted=False,
                source_location_ready=True,
            ),
            SimpleNamespace(
                candidate_id="eligible",
                role="verification",
                source_text="B",
                source_name="b.pdf",
                adapter_accepted=True,
                source_location_ready=True,
            ),
        ]

        analysis = SimpleNamespace(
            candidates=candidates
        )

        grounded = SimpleNamespace(
            status="SUPPORTED",
            basis_type="TEST",
        )

        with patch(
            "src.application.role_grounding."
            "evaluate_candidate_role_grounding",
            return_value=grounded,
        ) as evaluator:
            result = ground_semantic_candidates(
                analysis,
                max_workers=4,
            )

        self.assertEqual(
            evaluator.call_count,
            1,
        )

        self.assertEqual(
            list(result),
            ["blocked", "eligible"],
        )


if __name__ == "__main__":
    unittest.main()
