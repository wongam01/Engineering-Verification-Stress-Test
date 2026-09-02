import unittest

from decimal import Decimal

from src.ai.numeric_normalizer import (
    canonicalize_numeric_literal,
    normalize_numeric_contract,
)

from src.ai.constraint_parser import (
    normalize_constraint
    as normalize_single_constraint,
)

from src.ai.multi_constraint_parser import (
    normalize_constraint
    as normalize_multi_constraint,
)


class NumericLiteralCanonicalizationTests(
    unittest.TestCase
):
    def test_plain_decimal_is_preserved(
        self,
    ):
        self.assertEqual(
            canonicalize_numeric_literal(
                "5"
            ),
            "5",
        )

        self.assertEqual(
            canonicalize_numeric_literal(
                "3.25"
            ),
            "3.25",
        )

    def test_native_scientific_notation_is_preserved(
        self,
    ):
        result = (
            canonicalize_numeric_literal(
                "1e-6"
            )
        )

        self.assertEqual(
            Decimal(result),
            Decimal("1e-6"),
        )

    def test_engineering_scientific_notation_is_canonicalized(
        self,
    ):
        samples = [
            "1x10-6",
            "1 x 10^-6",
            "1×10^-6",
            "1 * 10^-6",
        ]

        for sample in samples:
            with self.subTest(
                sample=sample
            ):
                result = (
                    canonicalize_numeric_literal(
                        sample
                    )
                )

                self.assertIsNotNone(
                    result
                )

                self.assertEqual(
                    Decimal(result),
                    Decimal("1e-6"),
                )

    def test_engineering_multiplier_is_not_reduced_to_scalar(
        self,
    ):
        self.assertIsNone(
            canonicalize_numeric_literal(
                "1.5xMEOP"
            )
        )

        self.assertIsNone(
            canonicalize_numeric_literal(
                "2.5xReferencePressure"
            )
        )


class NumericContractFailSafeTests(
    unittest.TestCase
):
    def test_non_literal_lower_bound_becomes_safe_unsupported(
        self,
    ):
        data = {
            "type": "lower_bound",
            "variable": "proof pressure",
            "unit": None,
            "min": "1.5xMEOP",
            "max": None,
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": False,
            "review_reason": None,
        }

        result = (
            normalize_numeric_contract(
                data
            )
        )

        self.assertEqual(
            result["type"],
            "unsupported",
        )

        self.assertTrue(
            result["needs_review"]
        )

        self.assertIsNone(
            result["min"]
        )

        self.assertIsNone(
            result["variable"]
        )

        self.assertIn(
            "1.5xMEOP",
            result[
                "review_reason"
            ],
        )

    def test_scientific_upper_bound_remains_executable_type(
        self,
    ):
        data = {
            "type": "upper_bound",
            "variable": "leak rate",
            "unit": "cc/sec",
            "min": None,
            "max": "1x10-6",
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": True,
            "review_reason": (
                "Strict inequality requires review."
            ),
        }

        result = (
            normalize_numeric_contract(
                data
            )
        )

        self.assertEqual(
            result["type"],
            "upper_bound",
        )

        self.assertEqual(
            Decimal(
                result["max"]
            ),
            Decimal("1e-6"),
        )

        self.assertTrue(
            result[
                "needs_review"
            ]
        )

        self.assertEqual(
            result[
                "review_reason"
            ],
            (
                "Strict inequality "
                "requires review."
            ),
        )


class ParserNumericContractIntegrationTests(
    unittest.TestCase
):
    def _scientific_case(
        self,
    ):
        return {
            "type": "upper_bound",
            "variable": "leak rate",
            "unit": "cc/sec",
            "min": None,
            "max": "1x10-6",
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": False,
            "review_reason": None,
        }

    def _multiplier_case(
        self,
    ):
        return {
            "type": "lower_bound",
            "variable": "proof pressure",
            "unit": None,
            "min": "1.5xReferencePressure",
            "max": None,
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": False,
            "review_reason": None,
        }

    def test_single_parser_scientific_normalization(
        self,
    ):
        result = (
            normalize_single_constraint(
                self._scientific_case()
            )
        )

        self.assertEqual(
            Decimal(
                result["max"]
            ),
            Decimal("1e-6"),
        )

    def test_multi_parser_scientific_normalization(
        self,
    ):
        result = (
            normalize_multi_constraint(
                self._scientific_case()
            )
        )

        self.assertEqual(
            Decimal(
                result["max"]
            ),
            Decimal("1e-6"),
        )

    def test_single_parser_multiplier_is_fail_safe(
        self,
    ):
        result = (
            normalize_single_constraint(
                self._multiplier_case()
            )
        )

        self.assertEqual(
            result["type"],
            "unsupported",
        )

        self.assertTrue(
            result["needs_review"]
        )

    def test_multi_parser_multiplier_is_fail_safe(
        self,
    ):
        result = (
            normalize_multi_constraint(
                self._multiplier_case()
            )
        )

        self.assertEqual(
            result["type"],
            "unsupported",
        )

        self.assertTrue(
            result["needs_review"]
        )


if __name__ == "__main__":
    unittest.main()