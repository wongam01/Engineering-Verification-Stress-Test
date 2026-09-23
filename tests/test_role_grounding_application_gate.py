import unittest

from src.application.role_grounding import (
    RoleGroundingResult,
    apply_grounded_semantic_approvals,
    build_grounded_feasible_evidence_prefills,
)


def grounding(
    candidate_id,
    role,
    status="SUPPORTED",
    basis_type="TEST_BASIS",
):
    return RoleGroundingResult(
        candidate_id=candidate_id,
        proposed_role=role,
        status=status,
        basis_type=basis_type,
        explanation="Test grounding result.",
        supporting_text="Source-backed evidence text.",
    )


class RoleGroundingApplicationGateTest(unittest.TestCase):

    def test_semantic_rejected_grounding_blocks_downstream(self):
        called = []

        def fake_apply(*args):
            called.append(args)
            return "SHOULD_NOT_RUN"

        result = apply_grounded_semantic_approvals(
            object(),
            object(),
            ["V1"],
            {
                "V1": grounding(
                    "V1",
                    "verification",
                    status="REJECTED",
                    basis_type="OPERATIONAL_LIMIT",
                )
            },
            apply_func=fake_apply,
        )

        self.assertTrue(
            result.grounding_blocked
        )
        self.assertIsNone(
            result.downstream_result
        )
        self.assertEqual(
            called,
            [],
        )

    def test_semantic_missing_grounding_blocks_downstream(self):
        called = []

        def fake_apply(*args):
            called.append(args)
            return "SHOULD_NOT_RUN"

        result = apply_grounded_semantic_approvals(
            object(),
            object(),
            ["R1"],
            {},
            apply_func=fake_apply,
        )

        self.assertTrue(
            result.grounding_blocked
        )
        self.assertIsNone(
            result.downstream_result
        )
        self.assertEqual(
            called,
            [],
        )

    def test_semantic_supported_grounding_reaches_existing_flow(self):
        calls = []

        def fake_apply(
            base_case,
            analysis,
            approved_ids,
        ):
            calls.append(
                (
                    base_case,
                    analysis,
                    approved_ids,
                )
            )
            return "SEMANTIC_OK"

        base_case = object()
        analysis = object()

        result = apply_grounded_semantic_approvals(
            base_case,
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
            apply_func=fake_apply,
        )

        self.assertFalse(
            result.grounding_blocked
        )
        self.assertEqual(
            result.downstream_result,
            "SEMANTIC_OK",
        )
        self.assertEqual(
            calls[0][2],
            ["R1", "V1"],
        )

    def test_feasible_rejected_grounding_blocks_prefill(self):
        called = []

        def fake_builder(*args, **kwargs):
            called.append(
                (args, kwargs)
            )
            return "SHOULD_NOT_RUN"

        result = (
            build_grounded_feasible_evidence_prefills(
                object(),
                approved_candidate_ids=["F1"],
                grounding_by_candidate_id={
                    "F1": grounding(
                        "F1",
                        "feasible",
                        status="REJECTED",
                        basis_type="DESIGN_TARGET",
                    )
                },
                canonical_variable_by_candidate={
                    "F1": "H"
                },
                prefill_builder=fake_builder,
            )
        )

        self.assertTrue(
            result.grounding_blocked
        )
        self.assertIsNone(
            result.downstream_result
        )
        self.assertEqual(
            called,
            [],
        )

    def test_feasible_supported_grounding_reaches_existing_flow(self):
        calls = []

        def fake_builder(
            analysis,
            *,
            approved_candidate_ids,
            canonical_variable_by_candidate,
        ):
            calls.append(
                (
                    analysis,
                    approved_candidate_ids,
                    canonical_variable_by_candidate,
                )
            )
            return "FEASIBLE_OK"

        analysis = object()

        result = (
            build_grounded_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=["F1"],
                grounding_by_candidate_id={
                    "F1": grounding(
                        "F1",
                        "feasible",
                    )
                },
                canonical_variable_by_candidate={
                    "F1": "H"
                },
                prefill_builder=fake_builder,
            )
        )

        self.assertFalse(
            result.grounding_blocked
        )
        self.assertEqual(
            result.downstream_result,
            "FEASIBLE_OK",
        )
        self.assertEqual(
            calls[0][1],
            ["F1"],
        )
        self.assertEqual(
            calls[0][2],
            {"F1": "H"},
        )


if __name__ == "__main__":
    unittest.main()
