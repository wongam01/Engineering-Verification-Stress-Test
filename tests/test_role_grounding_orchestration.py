import unittest
from types import SimpleNamespace

from src.application.role_grounding import (
    ground_feasible_candidates,
    ground_semantic_candidates,
)


class RoleGroundingOrchestrationTest(unittest.TestCase):

    def test_semantic_candidates_preserve_proposed_roles(self):
        analysis = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    candidate_id="R1",
                    role="requirement",
                    source_text=(
                        "Hardness H shall be between "
                        "50 and 57 HRC."
                    ),
                    source_name="Requirement.pdf",
                ),
                SimpleNamespace(
                    candidate_id="V1",
                    role="verification",
                    source_text=(
                        "A part passes inspection when "
                        "H is at least 50 HRC."
                    ),
                    source_name="Inspection.pdf",
                ),
            ]
        )

        calls = []

        def evaluator(
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
                    "EXPLICIT_NORMATIVE_REQUIREMENT"
                    if proposed_role == "requirement"
                    else "EXPLICIT_ACCEPTANCE_CRITERION"
                ),
                "explanation": "Supported role.",
                "supporting_text": source_text,
            }

        results = ground_semantic_candidates(
            analysis,
            evaluator=evaluator,
        )

        self.assertEqual(
            set(results),
            {"R1", "V1"},
        )
        self.assertEqual(
            results["R1"].proposed_role,
            "requirement",
        )
        self.assertEqual(
            results["V1"].proposed_role,
            "verification",
        )
        self.assertEqual(
            [call[1] for call in calls],
            [
                "requirement",
                "verification",
            ],
        )

    def test_feasible_candidates_use_feasible_role(self):
        analysis = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    candidate_id="F1",
                    source_text=(
                        "Observed hardness H ranged "
                        "from 58 to 60 HRC."
                    ),
                    source_name="Measurements.pdf",
                )
            ]
        )

        calls = []

        def evaluator(
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
                    "OBSERVED_MEASUREMENT_EVIDENCE"
                ),
                "explanation": (
                    "Completed physical measurements."
                ),
                "supporting_text": source_text,
            }

        results = ground_feasible_candidates(
            analysis,
            evaluator=evaluator,
        )

        self.assertEqual(
            results["F1"].proposed_role,
            "feasible",
        )
        self.assertEqual(
            calls[0][1],
            "feasible",
        )

    def test_one_evaluator_failure_does_not_approve_candidate(self):
        analysis = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    candidate_id="V1",
                    role="verification",
                    source_text="Some criterion.",
                    source_name="source.pdf",
                )
            ]
        )

        def failing_evaluator(*_):
            raise RuntimeError(
                "simulated grounding failure"
            )

        results = ground_semantic_candidates(
            analysis,
            evaluator=failing_evaluator,
        )

        self.assertEqual(
            results["V1"].status,
            "REVIEW_REQUIRED",
        )
        self.assertFalse(
            results["V1"].supported
        )

    def test_empty_candidate_sets_return_empty_mapping(self):
        analysis = SimpleNamespace(
            candidates=[]
        )

        self.assertEqual(
            ground_semantic_candidates(
                analysis,
                evaluator=lambda *_: {},
            ),
            {},
        )

        self.assertEqual(
            ground_feasible_candidates(
                analysis,
                evaluator=lambda *_: {},
            ),
            {},
        )


if __name__ == "__main__":
    unittest.main()
