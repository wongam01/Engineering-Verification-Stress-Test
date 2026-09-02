import unittest
from decimal import Decimal

from src.core.models import EngineeringCase
from src.core.patch_engine import (
    constraint_passes_state,
    evaluate_patch,
    generate_patch_candidates,
)


def make_case(
    requirement: dict,
) -> EngineeringCase:
    return EngineeringCase.from_dict(
        {
            "name": "one sided patch engine test",
            "variables": {
                "P": {
                    "unit": "bar",
                    "nominal": "5",
                    "feasible_min": "0",
                    "feasible_max": "10",
                    "verification_min": "0",
                    "verification_max": "10",
                }
            },
            "requirements": [
                requirement,
            ],
            "verification_constraints": [],
        }
    )


class OneSidedBoundPatchEngineTests(
    unittest.TestCase
):
    def test_lower_bound_state_passes(self):
        case = make_case(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        requirement = case.requirements[0]

        self.assertTrue(
            constraint_passes_state(
                requirement,
                {
                    "P": Decimal("5"),
                },
            )
        )

        self.assertFalse(
            constraint_passes_state(
                requirement,
                {
                    "P": Decimal("3"),
                },
            )
        )

    def test_upper_bound_state_passes(self):
        case = make_case(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        requirement = case.requirements[0]

        self.assertTrue(
            constraint_passes_state(
                requirement,
                {
                    "P": Decimal("5"),
                },
            )
        )

        self.assertFalse(
            constraint_passes_state(
                requirement,
                {
                    "P": Decimal("7"),
                },
            )
        )

    def test_lower_bound_generic_patch_closes_escape(self):
        case = make_case(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        candidates = generate_patch_candidates(
            case,
            "R1",
        )

        self.assertGreaterEqual(
            len(candidates),
            1,
        )

        candidate = candidates[0]

        self.assertEqual(
            candidate.kind,
            "add_constraint",
        )
        self.assertIsNotNone(
            candidate.constraint
        )
        self.assertEqual(
            candidate.constraint.type,
            "lower_bound",
        )

        evaluation = evaluate_patch(
            case,
            candidate,
        )

        self.assertTrue(
            evaluation.valid_input
        )
        self.assertTrue(
            evaluation.closes_escape
        )
        self.assertTrue(
            evaluation.preserves_nominal
        )
        self.assertTrue(
            evaluation.model_closure_candidate
        )

    def test_upper_bound_generic_patch_closes_escape(self):
        case = make_case(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        candidates = generate_patch_candidates(
            case,
            "R2",
        )

        self.assertGreaterEqual(
            len(candidates),
            1,
        )

        candidate = candidates[0]

        self.assertEqual(
            candidate.kind,
            "add_constraint",
        )
        self.assertIsNotNone(
            candidate.constraint
        )
        self.assertEqual(
            candidate.constraint.type,
            "upper_bound",
        )

        evaluation = evaluate_patch(
            case,
            candidate,
        )

        self.assertTrue(
            evaluation.valid_input
        )
        self.assertTrue(
            evaluation.closes_escape
        )
        self.assertTrue(
            evaluation.preserves_nominal
        )
        self.assertTrue(
            evaluation.model_closure_candidate
        )


if __name__ == "__main__":
    unittest.main()