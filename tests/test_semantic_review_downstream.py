import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src.ai.core_adapter import (
    convert_ai_constraint,
)
from src.application.role_grounding import (
    RoleGroundingResult,
    apply_grounded_semantic_approvals,
    evaluate_role_completeness,
)


def extraction(
    *,
    role="requirement",
    constraint_type="range",
):
    return {
        "constraint_id": "UNSPECIFIED",
        "constraint_role": role,
        "type": constraint_type,
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


def candidate(
    candidate_id="candidate-1",
    role="requirement",
    constraint_type="range",
):
    data = extraction(
        role=role,
        constraint_type=constraint_type,
    )

    adapter = convert_ai_constraint(
        data
    )

    return SimpleNamespace(
        candidate_id=candidate_id,
        role=role,
        extraction=data,
        adapter_result=adapter,
        adapter_accepted=adapter.accepted,
        source_location_ready=True,
    )


def grounding(
    candidate_id="candidate-1",
    role="requirement",
):
    return RoleGroundingResult(
        candidate_id=candidate_id,
        proposed_role=role,
        status="SUPPORTED",
        basis_type="TEST_SUPPORTED",
        explanation="Supported.",
        supporting_text="source support",
    )


class SemanticReviewDownstreamTest(
    unittest.TestCase
):
    def test_reviewed_candidate_reaches_downstream_with_strict_adapter(
        self,
    ):
        original = candidate()

        self.assertFalse(
            original.adapter_accepted
        )

        analysis = SimpleNamespace(
            candidates=[original]
        )

        seen = {}

        def apply_func(
            base_case,
            reviewed_analysis,
            approved_ids,
        ):
            reviewed = (
                reviewed_analysis
                .candidates[0]
            )

            seen["accepted"] = (
                reviewed.adapter_result.accepted
            )
            seen["constraint_id"] = (
                reviewed
                .adapter_result
                .constraint
                .id
            )
            seen["approved_ids"] = (
                approved_ids
            )

            return "DOWNSTREAM_OK"

        result = apply_grounded_semantic_approvals(
            object(),
            analysis,
            [original.candidate_id],
            {
                original.candidate_id:
                grounding()
            },
            apply_func=apply_func,
        )

        self.assertFalse(
            result.grounding_blocked
        )
        self.assertEqual(
            result.downstream_result,
            "DOWNSTREAM_OK",
        )
        self.assertTrue(
            seen["accepted"]
        )
        self.assertTrue(
            seen["constraint_id"].startswith(
                "R_REVIEWED_"
            )
        )
        self.assertEqual(
            seen["approved_ids"],
            [original.candidate_id],
        )

        # Original analysis remains immutable.
        self.assertFalse(
            original.adapter_accepted
        )

    def test_strict_readaptation_failure_blocks_downstream(
        self,
    ):
        original = candidate(
            constraint_type="unsupported"
        )

        analysis = SimpleNamespace(
            candidates=[original]
        )

        apply_func = Mock()

        result = apply_grounded_semantic_approvals(
            object(),
            analysis,
            [original.candidate_id],
            {
                original.candidate_id:
                grounding()
            },
            apply_func=apply_func,
        )

        self.assertTrue(
            result.grounding_blocked
        )
        self.assertIsNone(
            result.downstream_result
        )
        apply_func.assert_not_called()

    def test_completeness_uses_strict_reviewed_adapter(
        self,
    ):
        requirement = candidate(
            candidate_id="r1",
            role="requirement",
        )

        analysis = SimpleNamespace(
            candidates=[requirement]
        )

        feasible_analysis = SimpleNamespace(
            candidates=[]
        )

        result = evaluate_role_completeness(
            semantic_analysis=analysis,
            approved_semantic_candidate_ids=[
                "r1"
            ],
            semantic_grounding_by_candidate_id={
                "r1": grounding(
                    candidate_id="r1",
                    role="requirement",
                )
            },
            feasible_analysis=feasible_analysis,
            approved_feasible_candidate_ids=[],
            feasible_grounding_by_candidate_id={},
        )

        self.assertTrue(
            result.requirement_established
        )

        self.assertIn(
            "r1",
            result.established_semantic_candidate_ids,
        )

        # Other required roles are intentionally absent.
        self.assertFalse(
            result.ready
        )

    def test_unapproved_candidate_is_not_established(
        self,
    ):
        requirement = candidate(
            candidate_id="r1",
            role="requirement",
        )

        result = evaluate_role_completeness(
            semantic_analysis=SimpleNamespace(
                candidates=[requirement]
            ),
            approved_semantic_candidate_ids=[],
            semantic_grounding_by_candidate_id={
                "r1": grounding(
                    candidate_id="r1",
                    role="requirement",
                )
            },
            feasible_analysis=SimpleNamespace(
                candidates=[]
            ),
            approved_feasible_candidate_ids=[],
            feasible_grounding_by_candidate_id={},
        )

        self.assertFalse(
            result.requirement_established
        )


if __name__ == "__main__":
    unittest.main()
