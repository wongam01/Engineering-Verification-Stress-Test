import unittest
from decimal import Decimal

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
    VariableSpec,
)
from src.core.validator import validate_case


def make_variable() -> VariableSpec:
    return VariableSpec.from_dict(
        {
            "unit": "bar",
            "nominal": "5",
            "feasible_min": "0",
            "feasible_max": "10",
            "verification_min": "0",
            "verification_max": "10",
        }
    )


class OneSidedBoundTests(unittest.TestCase):
    def test_lower_bound_model_references_variable(self):
        requirement = RequirementSpec.from_dict(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        self.assertEqual(
            requirement.referenced_variables(),
            ("P",),
        )

        self.assertEqual(
            requirement.to_dict(),
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": Decimal("4"),
            },
        )

    def test_upper_bound_model_references_variable(self):
        requirement = RequirementSpec.from_dict(
            {
                "id": "R1",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        self.assertEqual(
            requirement.referenced_variables(),
            ("P",),
        )

        self.assertEqual(
            requirement.to_dict(),
            {
                "id": "R1",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": Decimal("6"),
            },
        )

    def test_valid_lower_bound_passes_validation(self):
        case = EngineeringCase(
            name="lower bound valid",
            variables={
                "P": make_variable(),
            },
            requirements=[
                RequirementSpec.from_dict(
                    {
                        "id": "R1",
                        "type": "lower_bound",
                        "unit": "bar",
                        "variable": "P",
                        "min": "4",
                    }
                )
            ],
        )

        result = validate_case(case)

        self.assertTrue(result.valid)

    def test_lower_bound_without_variable_fails(self):
        case = EngineeringCase(
            name="lower bound no variable",
            variables={
                "P": make_variable(),
            },
            requirements=[
                RequirementSpec.from_dict(
                    {
                        "id": "R1",
                        "type": "lower_bound",
                        "unit": "bar",
                        "min": "4",
                    }
                )
            ],
        )

        result = validate_case(case)

        self.assertFalse(result.valid)

    def test_lower_bound_without_min_fails(self):
        case = EngineeringCase(
            name="lower bound no min",
            variables={
                "P": make_variable(),
            },
            requirements=[
                RequirementSpec.from_dict(
                    {
                        "id": "R1",
                        "type": "lower_bound",
                        "unit": "bar",
                        "variable": "P",
                    }
                )
            ],
        )

        result = validate_case(case)

        self.assertFalse(result.valid)

    def test_valid_upper_bound_passes_validation(self):
        case = EngineeringCase(
            name="upper bound valid",
            variables={
                "P": make_variable(),
            },
            requirements=[
                RequirementSpec.from_dict(
                    {
                        "id": "R1",
                        "type": "upper_bound",
                        "unit": "bar",
                        "variable": "P",
                        "max": "6",
                    }
                )
            ],
        )

        result = validate_case(case)

        self.assertTrue(result.valid)

    def test_upper_bound_without_variable_fails(self):
        case = EngineeringCase(
            name="upper bound no variable",
            variables={
                "P": make_variable(),
            },
            requirements=[
                RequirementSpec.from_dict(
                    {
                        "id": "R1",
                        "type": "upper_bound",
                        "unit": "bar",
                        "max": "6",
                    }
                )
            ],
        )

        result = validate_case(case)

        self.assertFalse(result.valid)

    def test_upper_bound_without_max_fails(self):
        case = EngineeringCase(
            name="upper bound no max",
            variables={
                "P": make_variable(),
            },
            requirements=[
                RequirementSpec.from_dict(
                    {
                        "id": "R1",
                        "type": "upper_bound",
                        "unit": "bar",
                        "variable": "P",
                    }
                )
            ],
        )

        result = validate_case(case)

        self.assertFalse(result.valid)


if __name__ == "__main__":
    unittest.main()