import unittest
from copy import deepcopy
from types import SimpleNamespace

from src.ai.core_adapter import (
    convert_ai_constraint,
)
from src.application.role_grounding import (
    RoleGroundingResult,
    build_engineer_reviewed_semantic_adapter,
)


def supported_grounding(
    candidate_id,
    role,
):
    return RoleGroundingResult(
        candidate_id=candidate_id,
        proposed_role=role,
        status="SUPPORTED",
        basis_type="TEST_SUPPORTED",
        explanation="Source supports the proposed role.",
        supporting_text="source support",
    )


def build_candidate(
    *,
    candidate_id="candidate-1",
    role="requirement",
    extraction=None,
    source_ready=True,
):
    if extraction is None:
        extraction = {
            "constraint_id": "UNSPECIFIED",
            "constraint_role": role,
            "type": "range",
            "variable": "Tip hardness",
            "min": "50",
            "max": "57",
            "unit": "HRC",
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": True,
            "review_reason": (
                "Constraint ID is not explicitly provided."
            ),
            "source_name": "source.pdf",
            "source_text": (
                "Tip hardness spec changed to 50-57 HRC."
            ),
        }

    original_adapter = convert_ai_constraint(
        extraction
    )

    return SimpleNamespace(
        candidate_id=candidate_id,
        role=role,
        extraction=extraction,
        adapter_result=original_adapter,
        adapter_accepted=original_adapter.accepted,
        source_location_ready=source_ready,
    )


class SemanticReviewReadaptationTest(
    unittest.TestCase
):
    def test_review_required_candidate_can_be_strictly_readapted(
        self,
    ):
        candidate = build_candidate()
        original = deepcopy(
            candidate.extraction
        )

        self.assertFalse(
            candidate.adapter_accepted
        )

        result = (
            build_engineer_reviewed_semantic_adapter(
                candidate,
                supported_grounding(
                    candidate.candidate_id,
                    candidate.role,
                ),
            )
        )

        self.assertIsNotNone(result)
        self.assertTrue(result.accepted)
        self.assertIsNotNone(result.constraint)

        self.assertTrue(
            result.constraint.id.startswith(
                "R_REVIEWED_"
            )
        )

        # Original AI extraction is never mutated.
        self.assertEqual(
            candidate.extraction,
            original,
        )

    def test_generated_id_is_deterministic(self):
        candidate = build_candidate(
            candidate_id="same-candidate"
        )

        grounding = supported_grounding(
            candidate.candidate_id,
            candidate.role,
        )

        first = (
            build_engineer_reviewed_semantic_adapter(
                candidate,
                grounding,
            )
        )

        second = (
            build_engineer_reviewed_semantic_adapter(
                candidate,
                grounding,
            )
        )

        self.assertTrue(first.accepted)
        self.assertTrue(second.accepted)
        self.assertEqual(
            first.constraint.id,
            second.constraint.id,
        )

    def test_existing_constraint_id_is_preserved(self):
        candidate = build_candidate()

        candidate.extraction[
            "constraint_id"
        ] = "R_HARDNESS"

        result = (
            build_engineer_reviewed_semantic_adapter(
                candidate,
                supported_grounding(
                    candidate.candidate_id,
                    candidate.role,
                ),
            )
        )

        self.assertTrue(result.accepted)
        self.assertEqual(
            result.constraint.id,
            "R_HARDNESS",
        )

    def test_unsupported_semantics_remain_blocked(self):
        candidate = build_candidate()

        candidate.extraction["type"] = "unsupported"

        result = (
            build_engineer_reviewed_semantic_adapter(
                candidate,
                supported_grounding(
                    candidate.candidate_id,
                    candidate.role,
                ),
            )
        )

        self.assertIsNotNone(result)
        self.assertFalse(result.accepted)

    def test_non_supported_grounding_cannot_readapt(self):
        candidate = build_candidate()

        grounding = RoleGroundingResult(
            candidate_id=candidate.candidate_id,
            proposed_role=candidate.role,
            status="REVIEW_REQUIRED",
            basis_type="AMBIGUOUS_ROLE_CONTEXT",
            explanation="Ambiguous.",
            supporting_text="",
        )

        result = (
            build_engineer_reviewed_semantic_adapter(
                candidate,
                grounding,
            )
        )

        self.assertIsNone(result)

    def test_unresolved_source_cannot_readapt(self):
        candidate = build_candidate(
            source_ready=False
        )

        result = (
            build_engineer_reviewed_semantic_adapter(
                candidate,
                supported_grounding(
                    candidate.candidate_id,
                    candidate.role,
                ),
            )
        )

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
