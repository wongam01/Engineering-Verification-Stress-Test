import unittest

from src.ai.constraint_parser import (
    ConstraintExtraction,
    normalize_constraint,
)


def make_data(
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
    }

    data.update(overrides)
    return data


class OneSidedBoundConstraintParserTests(unittest.TestCase):
    def test_schema_accepts_lower_bound(self):
        item = ConstraintExtraction(
            **make_data(
                "lower_bound",
                min="4",
            )
        )

        self.assertEqual(
            item.type,
            "lower_bound",
        )
        self.assertEqual(
            item.variable,
            "P",
        )
        self.assertEqual(
            item.min,
            "4",
        )

    def test_schema_accepts_upper_bound(self):
        item = ConstraintExtraction(
            **make_data(
                "upper_bound",
                max="6",
            )
        )

        self.assertEqual(
            item.type,
            "upper_bound",
        )
        self.assertEqual(
            item.variable,
            "P",
        )
        self.assertEqual(
            item.max,
            "6",
        )

    def test_lower_bound_normalization_preserves_min(self):
        data = make_data(
            "lower_bound",
            min="4",
        )

        result = normalize_constraint(
            data
        )

        self.assertEqual(
            result["min"],
            "4",
        )
        self.assertIsNone(
            result["max"]
        )
        self.assertIsNone(
            result["limit"]
        )

    def test_upper_bound_normalization_preserves_max(self):
        data = make_data(
            "upper_bound",
            max="6",
        )

        result = normalize_constraint(
            data
        )

        self.assertEqual(
            result["max"],
            "6",
        )
        self.assertIsNone(
            result["min"]
        )
        self.assertIsNone(
            result["limit"]
        )


if __name__ == "__main__":
    unittest.main()