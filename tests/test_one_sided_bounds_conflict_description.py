import unittest

from src.core.conflict_analyzer import (
    build_requirement_description,
)
from src.core.models import RequirementSpec


class OneSidedBoundConflictDescriptionTests(
    unittest.TestCase
):
    def test_lower_bound_description(self):
        requirement = RequirementSpec.from_dict(
            {
                "id": "R1",
                "type": "lower_bound",
                "unit": "bar",
                "variable": "P",
                "min": "4",
            }
        )

        description = (
            build_requirement_description(
                requirement
            )
        )

        self.assertEqual(
            description,
            "R1: P >= 4 bar",
        )

    def test_upper_bound_description(self):
        requirement = RequirementSpec.from_dict(
            {
                "id": "R2",
                "type": "upper_bound",
                "unit": "bar",
                "variable": "P",
                "max": "6",
            }
        )

        description = (
            build_requirement_description(
                requirement
            )
        )

        self.assertEqual(
            description,
            "R2: P <= 6 bar",
        )


if __name__ == "__main__":
    unittest.main()