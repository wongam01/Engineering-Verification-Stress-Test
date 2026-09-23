import unittest
from types import SimpleNamespace

from src.application.role_grounding import (
    RoleGroundingResult,
    evaluate_role_completeness,
)


def grounding(
    candidate_id,
    role,
    status="SUPPORTED",
):
    return RoleGroundingResult(
        candidate_id=candidate_id,
        proposed_role=role,
        status=status,
        basis_type="TEST_BASIS",
        explanation="test grounding",
        supporting_text=(
            "source-supported text"
            if status == "SUPPORTED"
            else ""
        ),
    )


def semantic_candidate(
    candidate_id,
    role,
):
    return SimpleNamespace(
        candidate_id=candidate_id,
        role=role,
        adapter_accepted=True,
        source_location_ready=True,
    )


def feasible_candidate(
    candidate_id="F1",
    needs_review=False,
):
    return SimpleNamespace(
        candidate_id=candidate_id,
        source_location_ready=True,
        extraction={
            "needs_review": needs_review,
        },
    )


class RoleGroundingCompletenessTest(
    unittest.TestCase
):
    def test_all_three_roles_can_be_established(self):
        analysis = SimpleNamespace(
            candidates=[
                semantic_candidate(
                    "R1",
                    "requirement",
                ),
                semantic_candidate(
                    "V1",
                    "verification",
                ),
            ]
        )

        feasible = SimpleNamespace(
            candidates=[
                feasible_candidate("F1")
            ]
        )

        result = evaluate_role_completeness(
            analysis,
            ["R1", "V1"],
            {
                "R1": grounding(
                    "R1",
                    "requirement",
                ),
                "V1": grounding(
                    "V1",
                    "verification",
                ),
            },
            feasible,
            ["F1"],
            {
                "F1": grounding(
                    "F1",
                    "feasible",
                ),
            },
        )

        self.assertTrue(result.ready)
        self.assertTrue(
            result.requirement_established
        )
        self.assertTrue(
            result.verification_established
        )
        self.assertTrue(
            result.feasible_established
        )

    def test_found_does_not_mean_established(self):
        analysis = SimpleNamespace(
            candidates=[
                semantic_candidate(
                    "R1",
                    "requirement",
                ),
                semantic_candidate(
                    "V1",
                    "verification",
                ),
            ]
        )

        feasible = SimpleNamespace(
            candidates=[
                feasible_candidate("F1")
            ]
        )

        result = evaluate_role_completeness(
            analysis,
            ["R1", "V1"],
            {
                "R1": grounding(
                    "R1",
                    "requirement",
                ),
                "V1": grounding(
                    "V1",
                    "verification",
                    status="REJECTED",
                ),
            },
            feasible,
            ["F1"],
            {
                "F1": grounding(
                    "F1",
                    "feasible",
                ),
            },
        )

        self.assertEqual(
            result.verification_candidate_count,
            1,
        )
        self.assertFalse(
            result.verification_established
        )
        self.assertFalse(result.ready)

    def test_supported_but_unapproved_is_not_established(self):
        analysis = SimpleNamespace(
            candidates=[
                semantic_candidate(
                    "R1",
                    "requirement",
                ),
                semantic_candidate(
                    "V1",
                    "verification",
                ),
            ]
        )

        result = evaluate_role_completeness(
            analysis,
            ["R1"],
            {
                "R1": grounding(
                    "R1",
                    "requirement",
                ),
                "V1": grounding(
                    "V1",
                    "verification",
                ),
            },
            None,
            [],
            {},
        )

        self.assertFalse(
            result.verification_established
        )
        self.assertFalse(result.ready)

    def test_review_required_feasible_evidence_is_not_established(self):
        analysis = SimpleNamespace(
            candidates=[
                semantic_candidate(
                    "R1",
                    "requirement",
                ),
                semantic_candidate(
                    "V1",
                    "verification",
                ),
            ]
        )

        feasible = SimpleNamespace(
            candidates=[
                feasible_candidate(
                    "F1",
                    needs_review=True,
                )
            ]
        )

        result = evaluate_role_completeness(
            analysis,
            ["R1", "V1"],
            {
                "R1": grounding(
                    "R1",
                    "requirement",
                ),
                "V1": grounding(
                    "V1",
                    "verification",
                ),
            },
            feasible,
            ["F1"],
            {
                "F1": grounding(
                    "F1",
                    "feasible",
                ),
            },
        )

        self.assertFalse(
            result.feasible_established
        )
        self.assertFalse(result.ready)


if __name__ == "__main__":
    unittest.main()
