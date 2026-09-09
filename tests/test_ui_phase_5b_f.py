from pathlib import Path
import unittest


APP = Path(
    "src/ui/app.py"
).read_text()


class UiPhase5BFeasibleTest(
    unittest.TestCase
):
    def test_01_operating_evidence_pdf_uploader_exists(self):
        self.assertIn(
            "Operating Evidence PDF 업로드",
            APP,
        )
        self.assertIn(
            '"feasible",',
            APP,
        )

    def test_02_feasible_pdf_uses_separate_analysis_path(self):
        self.assertIn(
            "analyze_feasible_evidence_pdf",
            APP,
        )
        self.assertIn(
            "build_semantic_document(document)",
            APP,
        )
        self.assertIn(
            'if document.role in {',
            APP,
        )

    def test_03_feasible_source_review_is_separate(self):
        self.assertIn(
            "confirm_ambiguous_feasible_source_location",
            APP,
        )
        self.assertIn(
            "feasible_source_location_confirm_",
            APP,
        )

    def test_04_feasible_candidate_requires_engineer_approval(self):
        self.assertIn(
            "Feasible Domain 후보로 승인합니다.",
            APP,
        )
        self.assertIn(
            "feasible_approved_candidate_ids",
            APP,
        )
        self.assertIn(
            "EngineeringCase나 Solver에 아직 적용하지 않습니다.",
            APP,
        )


    def test_05_source_bound_f_prefill_is_present(self):
        self.assertIn(
            "build_source_reference",
            APP,
        )
        self.assertIn(
            "Feasible Domain Review",
            APP,
        )
        self.assertIn(
            "PDF Source Bound",
            APP,
        )

    def test_06_source_bound_f_is_review_only(self):
        self.assertIn(
            "Feasible Domain Review",
            APP,
        )
        self.assertIn(
            "Formal Feasible Domain",
            APP,
        )
        self.assertIn(
            "PDF Source Bound",
            APP,
        )
        self.assertIn(
            "Engineer Approved",
            APP,
        )

    def test_07_manual_f_fallback_is_preserved(self):
        self.assertIn(
            "Advanced · Engineer-Supplied",
            APP,
        )
        self.assertIn(
            "Feasible Domain",
            APP,
        )


    def test_08_application_prefill_contract_is_rechecked(self):
        self.assertIn(
            "build_feasible_evidence_prefills",
            APP,
        )
        self.assertIn(
            "canonical_variable_by_candidate",
            APP,
        )
        self.assertIn(
            "Application-level source-bound",
            APP,
        )

    def test_09_f_review_invalidates_prepared_model(self):
        self.assertIn(
            "prepared_feasible_review_signature",
            APP,
        )
        self.assertIn(
            "current_feasible_review_signature",
            APP,
        )

    def test_10_f_unit_conflict_is_blocked(self):
        self.assertIn(
            "conflicts with R/V unit(s)",
            APP,
        )


if __name__ == "__main__":
    unittest.main()
