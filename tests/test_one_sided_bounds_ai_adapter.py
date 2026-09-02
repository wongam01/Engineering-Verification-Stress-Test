import unittest
from decimal import Decimal

from src.ai.core_adapter import (
    convert_ai_constraint,
    validate_ai_extraction_structure,
)


def make_extraction(
    constraint_type: str,
    **overrides,
) -> dict:
    data = {
        "constraint_id": "R1",
        "type": constraint_type,
        "unit": "bar",
        "variable": "P",
        "min": None,
        "max": None,
        "left": None,
        "right": None,
        "variables": [],
        "limit": None,
        "needs_review": False,
        "review_reason": None,
        "constraint_role": "requirement",
        "source_name": "test_source",
        "source_text": "test engineering requirement",
    }

    data.update(overrides)

    return data


class OneSidedBoundAIAdapterTests(unittest.TestCase):
    def test_lower_bound_structure_valid(self):
        extraction = make_extraction(
            "lower_bound",
            min="4",
        )

        valid, message = (
            validate_ai_extraction_structure(
                extraction
            )
        )

        self.assertTrue(valid)
        self.assertEqual(message, "")

    def test_lower_bound_missing_min_rejected(self):
        extraction = make_extraction(
            "lower_bound",
            min=None,
        )

        valid, _ = (
            validate_ai_extraction_structure(
                extraction
            )
        )

        self.assertFalse(valid)

    def test_upper_bound_structure_valid(self):
        extraction = make_extraction(
            "upper_bound",
            max="6",
        )

        valid, message = (
            validate_ai_extraction_structure(
                extraction
            )
        )

        self.assertTrue(valid)
        self.assertEqual(message, "")

    def test_upper_bound_missing_max_rejected(self):
        extraction = make_extraction(
            "upper_bound",
            max=None,
        )

        valid, _ = (
            validate_ai_extraction_structure(
                extraction
            )
        )

        self.assertFalse(valid)

    def test_lower_bound_converts_to_core(self):
        extraction = make_extraction(
            "lower_bound",
            min="4",
        )

        result = convert_ai_constraint(
            extraction
        )

        self.assertTrue(result.accepted)
        self.assertIsNotNone(result.constraint)

        constraint = result.constraint

        self.assertEqual(
            constraint.type,
            "lower_bound",
        )
        self.assertEqual(
            constraint.variable,
            "P",
        )
        self.assertEqual(
            constraint.min_value,
            Decimal("4"),
        )

    def test_upper_bound_converts_to_core(self):
        extraction = make_extraction(
            "upper_bound",
            max="6",
        )

        result = convert_ai_constraint(
            extraction
        )

        self.assertTrue(result.accepted)
        self.assertIsNotNone(result.constraint)

        constraint = result.constraint

        self.assertEqual(
            constraint.type,
            "upper_bound",
        )
        self.assertEqual(
            constraint.variable,
            "P",
        )
        self.assertEqual(
            constraint.max_value,
            Decimal("6"),
        )


if __name__ == "__main__":
    unittest.main()