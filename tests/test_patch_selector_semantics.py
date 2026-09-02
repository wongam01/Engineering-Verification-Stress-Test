import unittest
from unittest.mock import patch

from src.core.json_io import (
    load_engineering_case,
)

from src.core.patch_engine import (
    evaluate_patch_candidates,
    select_model_closure_candidate,
    select_practical_patch,
)

from src.core.pipeline import (
    run_pipeline,
)


class PatchSelectorSemanticsTest(
    unittest.TestCase
):

    def setUp(self):
        self.case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

    # =====================================================
    # OFFICIAL SELECTOR
    # =====================================================

    def test_01_official_selector_uses_model_closure(
        self,
    ):
        evaluations = (
            evaluate_patch_candidates(
                self.case,
                "R2",
            )
        )

        selected = (
            select_model_closure_candidate(
                evaluations
            )
        )

        self.assertIsNotNone(
            selected
        )

        self.assertTrue(
            selected.model_closure_candidate
        )

        self.assertTrue(
            selected.engineering_review_required
        )

    # =====================================================
    # LEGACY COMPATIBILITY
    # =====================================================

    def test_02_legacy_selector_matches_official_selector(
        self,
    ):
        evaluations = (
            evaluate_patch_candidates(
                self.case,
                "R2",
            )
        )

        official = (
            select_model_closure_candidate(
                evaluations
            )
        )

        legacy = (
            select_practical_patch(
                evaluations
            )
        )

        self.assertIsNotNone(
            official
        )

        self.assertIsNotNone(
            legacy
        )

        self.assertEqual(
            official.candidate.patch_id,
            legacy.candidate.patch_id,
        )

        self.assertEqual(
            official.model_closure_candidate,
            legacy.model_closure_candidate,
        )

    # =====================================================
    # PIPELINE USES OFFICIAL API
    # =====================================================

    def test_03_pipeline_uses_model_closure_selector(
        self,
    ):
        with patch(
            "src.core.pipeline."
            "select_model_closure_candidate",
            wraps=(
                select_model_closure_candidate
            ),
        ) as mocked_selector:

            result = run_pipeline(
                self.case,
                generate_patches=True,
            )

        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            mocked_selector.called
        )


if __name__ == "__main__":
    unittest.main()