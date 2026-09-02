import unittest

from src.core.models import EngineeringCase
from src.core.stress_tester import (
    stress_test_requirement,
)


def make_case(
    requirement: dict,
    verification_min: str = "0",
    verification_max: str = "10",
) -> EngineeringCase:
    return EngineeringCase.from_dict(
        {
            "name": "one sided bound stress test",
            "variables": {
                "P": {
                    "unit": "bar",
                    "nominal": "5",
                    "feasible_min": "0",
                    "feasible_max": "10",
                    "verification_min": verification_min,
                    "verification_max": verification_max,
                }
            },
            "requirements": [
                requirement,
            ],
            "verification_constraints": [],
        }
    )


class OneSidedBoundStressTests(unittest.TestCase):
    def test_lower_bound_escape_found(self):
        case = make_case(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        result = stress_test_requirement(
            case,
            case.requirements[0],
        )

        self.assertTrue(
            result.escape_found
        )
        self.assertEqual(
            result.direction,
            "below_minimum",
        )
        self.assertAlmostEqual(
            result.worst_violation,
            4.0,
        )
        self.assertAlmostEqual(
            result.actual_value,
            0.0,
        )

    def test_lower_bound_no_escape(self):
        case = make_case(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            },
            verification_min="4",
            verification_max="10",
        )

        result = stress_test_requirement(
            case,
            case.requirements[0],
        )

        self.assertFalse(
            result.escape_found
        )

    def test_upper_bound_escape_found(self):
        case = make_case(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        result = stress_test_requirement(
            case,
            case.requirements[0],
        )

        self.assertTrue(
            result.escape_found
        )
        self.assertEqual(
            result.direction,
            "above_maximum",
        )
        self.assertAlmostEqual(
            result.worst_violation,
            4.0,
        )
        self.assertAlmostEqual(
            result.actual_value,
            10.0,
        )

    def test_upper_bound_no_escape(self):
        case = make_case(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            },
            verification_min="0",
            verification_max="6",
        )

        result = stress_test_requirement(
            case,
            case.requirements[0],
        )

        self.assertFalse(
            result.escape_found
        )


if __name__ == "__main__":
    unittest.main()