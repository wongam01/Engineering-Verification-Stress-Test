import unittest

from src.application.role_grounding import (
    apply_role_grounding_gate,
    evaluate_candidate_role_grounding,
    normalize_role_grounding_payload,
)


class RoleGroundingTest(unittest.TestCase):

    def test_explicit_requirement_can_be_supported(self):
        result = normalize_role_grounding_payload(
            candidate_id="R1",
            proposed_role="requirement",
            payload={
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_NORMATIVE_REQUIREMENT"
                ),
                "explanation": (
                    "The source states a normative engineering "
                    "requirement."
                ),
                "supporting_text": (
                    "Hardness H shall be between "
                    "50 HRC and 57 HRC inclusive."
                ),
            },
        )

        self.assertEqual(
            result.status,
            "SUPPORTED",
        )
        self.assertTrue(result.supported)

    def test_explicit_verification_can_be_supported(self):
        result = normalize_role_grounding_payload(
            candidate_id="V1",
            proposed_role="verification",
            payload={
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": (
                    "The source explicitly defines an "
                    "inspection pass criterion."
                ),
                "supporting_text": (
                    "A part passes the hardness inspection "
                    "when hardness H is at least 50 HRC."
                ),
            },
        )

        self.assertEqual(
            result.status,
            "SUPPORTED",
        )

    def test_observed_measurement_can_be_supported(self):
        result = normalize_role_grounding_payload(
            candidate_id="F1",
            proposed_role="feasible",
            payload={
                "status": "SUPPORTED",
                "basis_type": (
                    "OBSERVED_MEASUREMENT_EVIDENCE"
                ),
                "explanation": (
                    "The source reports completed physical "
                    "measurements."
                ),
                "supporting_text": (
                    "Observed hardness H ranged from "
                    "58 HRC to 60 HRC."
                ),
            },
        )

        self.assertEqual(
            result.status,
            "SUPPORTED",
        )

    def test_operational_limit_as_verification_is_blocked(self):
        result = normalize_role_grounding_payload(
            candidate_id="V_OPERATIONAL_LIMIT",
            proposed_role="verification",
            payload={
                "status": "REJECTED",
                "basis_type": "OPERATIONAL_LIMIT",
                "explanation": (
                    "The source describes an operating limit, "
                    "not an inspection or acceptance "
                    "PASS/FAIL criterion."
                ),
                "supporting_text": (
                    "Normal Operating Limit: 790 F."
                ),
            },
        )

        gate = apply_role_grounding_gate(
            approved_candidate_ids=[
                "V_OPERATIONAL_LIMIT"
            ],
            grounding_by_candidate_id={
                result.candidate_id: result
            },
        )

        self.assertEqual(
            result.status,
            "REJECTED",
        )
        self.assertEqual(
            gate.eligible_candidate_ids,
            (),
        )
        self.assertTrue(gate.issues)

    def test_ambiguous_role_is_review_required_and_blocked(self):
        result = normalize_role_grounding_payload(
            candidate_id="V_AMBIGUOUS",
            proposed_role="verification",
            payload={
                "status": "REVIEW_REQUIRED",
                "basis_type": "AMBIGUOUS_ROLE_CONTEXT",
                "explanation": (
                    "The source mentions a test criterion but "
                    "does not establish whether it determines "
                    "acceptance."
                ),
                "supporting_text": (
                    "The 150 psi criterion was used "
                    "during testing."
                ),
            },
        )

        gate = apply_role_grounding_gate(
            approved_candidate_ids=[
                "V_AMBIGUOUS"
            ],
            grounding_by_candidate_id={
                result.candidate_id: result
            },
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )
        self.assertEqual(
            gate.eligible_candidate_ids,
            (),
        )

    def test_unknown_role_is_preserved_and_blocked(self):
        result = normalize_role_grounding_payload(
            candidate_id="X1",
            proposed_role="operational",
            payload={
                "status": "SUPPORTED",
                "basis_type": "SOME_BASIS",
                "explanation": "Some explanation.",
                "supporting_text": "Some source text.",
            },
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )
        self.assertEqual(
            result.proposed_role,
            "operational",
        )
        self.assertFalse(result.supported)

    def test_missing_grounding_fails_safe(self):
        gate = apply_role_grounding_gate(
            approved_candidate_ids=["R1"],
            grounding_by_candidate_id={},
        )

        self.assertEqual(
            gate.eligible_candidate_ids,
            (),
        )
        self.assertIn(
            "Role Grounding is missing",
            gate.issues[0],
        )

    def test_malformed_supported_result_fails_safe(self):
        result = normalize_role_grounding_payload(
            candidate_id="V1",
            proposed_role="verification",
            payload={
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": (
                    "Explicit acceptance criterion."
                ),
                "supporting_text": "",
            },
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )
        self.assertFalse(result.supported)

    def test_application_evaluator_wrapper_normalizes_result(self):
        calls = []

        def fake_evaluator(
            source_text,
            proposed_role,
            source_name,
        ):
            calls.append(
                (
                    source_text,
                    proposed_role,
                    source_name,
                )
            )
            return {
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": (
                    "The source explicitly defines inspection "
                    "acceptance."
                ),
                "supporting_text": (
                    "passes the hardness inspection when "
                    "hardness H is at least 50 HRC"
                ),
            }

        result = evaluate_candidate_role_grounding(
            candidate_id="V1",
            proposed_role="verification",
            source_text=(
                "A part passes the hardness inspection when "
                "hardness H is at least 50 HRC."
            ),
            source_name="Inspection_Plan.pdf",
            evaluator=fake_evaluator,
        )

        self.assertEqual(
            result.status,
            "SUPPORTED",
        )
        self.assertEqual(
            result.proposed_role,
            "verification",
        )
        self.assertEqual(
            len(calls),
            1,
        )

    def test_application_evaluator_failure_fails_safe(self):
        def failing_evaluator(*_):
            raise RuntimeError("simulated evaluator failure")

        result = evaluate_candidate_role_grounding(
            candidate_id="V1",
            proposed_role="verification",
            source_text="Some source text.",
            source_name="source.pdf",
            evaluator=failing_evaluator,
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )
        self.assertEqual(
            result.basis_type,
            "GROUNDING_EVALUATOR_ERROR",
        )
        self.assertFalse(result.supported)

    def test_supported_grounding_requires_source_backed_quote(self):
        def fake_evaluator(
            source_text,
            proposed_role,
            source_name,
        ):
            return {
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": (
                    "The source explicitly defines acceptance."
                ),
                "supporting_text": (
                    "This sentence does not exist "
                    "in the supplied source."
                ),
            }

        result = evaluate_candidate_role_grounding(
            candidate_id="V1",
            proposed_role="verification",
            source_text=(
                "A part passes inspection when "
                "hardness H is at least 50 HRC."
            ),
            source_name="Inspection.pdf",
            evaluator=fake_evaluator,
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )
        self.assertEqual(
            result.basis_type,
            "GROUNDING_SOURCE_TEXT_MISMATCH",
        )
        self.assertFalse(result.supported)

    def test_supported_grounding_passes_gate(self):
        result = normalize_role_grounding_payload(
            candidate_id="V1",
            proposed_role="verification",
            payload={
                "status": "SUPPORTED",
                "basis_type": (
                    "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": (
                    "Explicit inspection acceptance criterion."
                ),
                "supporting_text": (
                    "Passes inspection when H is "
                    "at least 50 HRC."
                ),
            },
        )

        gate = apply_role_grounding_gate(
            approved_candidate_ids=["V1"],
            grounding_by_candidate_id={
                "V1": result,
            },
        )

        self.assertEqual(
            gate.eligible_candidate_ids,
            ("V1",),
        )
        self.assertEqual(
            gate.issues,
            (),
        )


if __name__ == "__main__":
    unittest.main()
