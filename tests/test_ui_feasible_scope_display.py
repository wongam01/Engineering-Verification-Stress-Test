import unittest
from pathlib import Path


APP = Path("src/ui/app.py")


class UiFeasibleScopeDisplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = APP.read_text(encoding="utf-8")

    def test_01_feasible_domain_role_has_dedicated_ui(self):
        self.assertIn(
            'if evidence.role == "feasible_domain":',
            self.text,
        )

    def test_02_selected_analysis_scope_is_displayed(self):
        self.assertIn(
            "Analysis Scope · ",
            self.text,
        )

    def test_03_processed_vision_pages_are_displayed(self):
        self.assertIn(
            "Vision Analyzed Pages · ",
            self.text,
        )

    def test_04_unprocessed_candidate_pages_are_displayed(self):
        self.assertIn(
            "Unprocessed Candidate Pages · ",
            self.text,
        )

    def test_05_obsolete_phase_5b_manual_f_copy_is_removed(self):
        self.assertNotIn(
            "현재 Phase 5B-0에서는 F가 PDF에서 자동 ",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
