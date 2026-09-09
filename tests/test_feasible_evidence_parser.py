import unittest

from src.ai.feasible_evidence_parser import (
    finalize_feasible_evidence_items,
    normalize_feasible_evidence,
)


class FeasibleEvidenceParserTest(
    unittest.TestCase
):
    def test_01_valid_range_remains_candidate(self):
        result = normalize_feasible_evidence(
            {
                "source_line_id": "L1",
                "variable": "H",
                "min": "58",
                "max": "60",
                "unit": "HRC",
                "evidence_type":
                    "observed_test_data",
                "needs_review": False,
                "review_reason": None,
            }
        )

        self.assertFalse(
            result["needs_review"]
        )
        self.assertEqual(
            result["min"],
            "58",
        )
        self.assertEqual(
            result["max"],
            "60",
        )

    def test_02_reversed_range_requires_review(self):
        result = normalize_feasible_evidence(
            {
                "source_line_id": "L1",
                "variable": "H",
                "min": "60",
                "max": "58",
                "unit": "HRC",
                "evidence_type":
                    "observed_test_data",
                "needs_review": False,
                "review_reason": None,
            }
        )

        self.assertTrue(
            result["needs_review"]
        )
        self.assertIn(
            "minimum",
            result["review_reason"],
        )

    def test_03_missing_bound_requires_review(self):
        result = normalize_feasible_evidence(
            {
                "source_line_id": "L1",
                "variable": "H",
                "min": "58",
                "max": None,
                "unit": "HRC",
                "evidence_type":
                    "observed_test_data",
                "needs_review": False,
                "review_reason": None,
            }
        )

        self.assertTrue(
            result["needs_review"]
        )
        self.assertIn(
            "max",
            result["review_reason"],
        )

    def test_04_non_numeric_bound_requires_review(self):
        result = normalize_feasible_evidence(
            {
                "source_line_id": "L1",
                "variable": "H",
                "min": "fifty-eight",
                "max": "60",
                "unit": "HRC",
                "evidence_type":
                    "observed_test_data",
                "needs_review": False,
                "review_reason": None,
            }
        )

        self.assertTrue(
            result["needs_review"]
        )
        self.assertIn(
            "numeric literal",
            result["review_reason"],
        )

    def test_05_unsupported_candidate_requires_review(self):
        result = normalize_feasible_evidence(
            {
                "source_line_id": "L1",
                "variable": "H",
                "min": "58",
                "max": "60",
                "unit": "HRC",
                "evidence_type":
                    "unsupported",
                "needs_review": False,
                "review_reason": None,
            }
        )

        self.assertTrue(
            result["needs_review"]
        )

    def test_06_existing_source_line_is_bound_deterministically(self):
        results = (
            finalize_feasible_evidence_items(
                [
                    {
                        "source_line_id": "L7",
                        "variable": "H",
                        "min": "58",
                        "max": "60",
                        "unit": "HRC",
                        "evidence_type":
                            "manufacturing_record",
                        "needs_review": False,
                        "review_reason": None,
                    }
                ],
                source_map={
                    "L7": (
                        "Measured production hardness "
                        "ranged from 58 to 60 HRC."
                    )
                },
                source_name=(
                    "Operating_Evidence.pdf"
                ),
            )
        )

        self.assertEqual(
            len(results),
            1,
        )
        self.assertEqual(
            results[0]["source_name"],
            "Operating_Evidence.pdf",
        )
        self.assertEqual(
            results[0]["source_text"],
            (
                "Measured production hardness "
                "ranged from 58 to 60 HRC."
            ),
        )
        self.assertFalse(
            results[0]["needs_review"]
        )

    def test_07_unknown_source_line_fails_safe(self):
        results = (
            finalize_feasible_evidence_items(
                [
                    {
                        "source_line_id": "L99",
                        "variable": "H",
                        "min": "58",
                        "max": "60",
                        "unit": "HRC",
                        "evidence_type":
                            "observed_test_data",
                        "needs_review": False,
                        "review_reason": None,
                    }
                ],
                source_map={
                    "L1": "Known source."
                },
                source_name=(
                    "Operating_Evidence.pdf"
                ),
            )
        )

        self.assertTrue(
            results[0]["needs_review"]
        )
        self.assertEqual(
            results[0]["source_text"],
            "",
        )
        self.assertIn(
            "source_line_id",
            results[0]["review_reason"],
        )


if __name__ == "__main__":
    unittest.main()
