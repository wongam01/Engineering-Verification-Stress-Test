import unittest
from decimal import Decimal

from src.core.models import (
    EngineeringCase,
)

from src.core.pipeline import (
    run_pipeline,
)


class CoreRegressionTest(
    unittest.TestCase
):

    # =====================================================
    # CASE 1
    # 충분한 검사계획
    # =====================================================

    def test_01_no_escape(self):

        data = {
            "name": "No Escape Case",

            "variables": {
                "A": {
                    "unit": "mm",
                    "nominal": Decimal("10.00"),
                    "feasible_min": Decimal("9.50"),
                    "feasible_max": Decimal("10.50"),
                    "verification_min": Decimal("9.90"),
                    "verification_max": Decimal("10.10"),
                },

                "B": {
                    "unit": "mm",
                    "nominal": Decimal("20.00"),
                    "feasible_min": Decimal("19.50"),
                    "feasible_max": Decimal("20.50"),
                    "verification_min": Decimal("19.90"),
                    "verification_max": Decimal("20.10"),
                },
            },

            "requirements": [
                {
                    "id": "R1",
                    "type": "sum_upper",
                    "variables": [
                        "A",
                        "B",
                    ],
                    "unit": "mm",
                    "limit": Decimal("30.05"),
                }
            ],

            "verification_constraints": [
                {
                    "id": "V1",
                    "type": "sum_upper",
                    "variables": [
                        "A",
                        "B",
                    ],
                    "unit": "mm",
                    "limit": Decimal("30.05"),
                }
            ],
        }

        case = EngineeringCase.from_dict(
            data
        )

        result = run_pipeline(
            case
        )

        self.assertEqual(
            result.status,
            "NO_ESCAPE_FOUND",
        )

        self.assertFalse(
            result.has_escape
        )

    # =====================================================
    # CASE 2
    # 검사계획 허점
    # =====================================================

    def test_02_escape_and_patch(self):

        data = {
            "name": "Escape Case",

            "variables": {
                "A": {
                    "unit": "mm",
                    "nominal": Decimal("10.00"),
                    "feasible_min": Decimal("9.50"),
                    "feasible_max": Decimal("10.50"),
                    "verification_min": Decimal("9.90"),
                    "verification_max": Decimal("10.10"),
                },

                "B": {
                    "unit": "mm",
                    "nominal": Decimal("20.00"),
                    "feasible_min": Decimal("19.50"),
                    "feasible_max": Decimal("20.50"),
                    "verification_min": Decimal("19.90"),
                    "verification_max": Decimal("20.10"),
                },
            },

            "requirements": [
                {
                    "id": "R1",
                    "type": "sum_upper",
                    "variables": [
                        "A",
                        "B",
                    ],
                    "unit": "mm",
                    "limit": Decimal("30.05"),
                }
            ],

            "verification_constraints": [],
        }

        case = EngineeringCase.from_dict(
            data
        )

        result = run_pipeline(
            case
        )

        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            result.has_escape
        )

        requirement_result = (
            result.requirement_results[0]
        )

        self.assertAlmostEqual(
            requirement_result
            .stress_result
            .worst_violation,

            0.15,

            places=6,
        )

        self.assertIsNotNone(
            requirement_result
            .selected_patch
        )

        self.assertEqual(
            requirement_result
            .selected_patch
            .candidate
            .patch_id,

            "P1",
        )

    # =====================================================
    # CASE 3
    # 잘못된 입력
    # =====================================================

    def test_03_invalid_input(self):

        data = {
            "name": "Invalid Input Case",

            "variables": {
                "X": {
                    "unit": "mm",
                    "nominal": Decimal("10.00"),
                    "feasible_min": Decimal("9.50"),
                    "feasible_max": Decimal("10.50"),

                    # 일부러 min/max 반대로
                    "verification_min": Decimal("10.10"),
                    "verification_max": Decimal("9.90"),
                }
            },

            "requirements": [],

            "verification_constraints": [],
        }

        case = EngineeringCase.from_dict(
            data
        )

        result = run_pipeline(
            case
        )

        self.assertEqual(
            result.status,
            "INVALID_INPUT",
        )

        self.assertFalse(
            result.validation.valid
        )

    # =====================================================
    # CASE 4
    # 논리적 모순
    # =====================================================

    def test_04_inconsistent_model(self):

        data = {
            "name": "Conflict Case",

            "variables": {
                "X": {
                    "unit": "mm",
                    "nominal": Decimal("10.00"),
                    "feasible_min": Decimal("9.50"),
                    "feasible_max": Decimal("10.50"),
                    "verification_min": Decimal("9.90"),
                    "verification_max": Decimal("10.10"),
                },

                "Y": {
                    "unit": "mm",
                    "nominal": Decimal("30.00"),
                    "feasible_min": Decimal("29.50"),
                    "feasible_max": Decimal("30.50"),
                    "verification_min": Decimal("29.90"),
                    "verification_max": Decimal("30.10"),
                },
            },

            "requirements": [
                {
                    "id": "R1",
                    "type": "sum_upper",
                    "variables": [
                        "X",
                        "Y",
                    ],
                    "unit": "mm",
                    "limit": Decimal("38.90"),
                }
            ],

            "verification_constraints": [],
        }

        case = EngineeringCase.from_dict(
            data
        )

        result = run_pipeline(
            case
        )

        self.assertEqual(
            result.status,
            "INCONSISTENT_MODEL",
        )

        self.assertIsNotNone(
            result.consistency
        )

        self.assertFalse(
            result.consistency.consistent
        )

        self.assertGreater(
            len(
                result.consistency
                .conflict_items
            ),
            0,
        )


if __name__ == "__main__":
    unittest.main()
