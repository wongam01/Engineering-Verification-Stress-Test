from pathlib import Path
import unittest


APP = Path("src/ui/app.py").read_text(encoding="utf-8")


class UiPhase5CVisionTest(unittest.TestCase):
    def test_01_ui_imports_generic_vision_workflow(self):
        self.assertIn(
            "pdf_document_requires_vision",
            APP,
        )
        self.assertIn(
            "pdf_document_can_attempt_vision",
            APP,
        )
        self.assertIn(
            "prepare_pdf_document_for_semantic_analysis",
            APP,
        )
        self.assertIn(
            "extract_pdf_page_with_vision",
            APP,
        )


    def test_02_vision_prepared_documents_are_cached(self):
        self.assertIn(
            '"vision_prepared_pdf_documents"',
            APP,
        )
        self.assertIn(
            '"vision_prepared_pdf_signature"',
            APP,
        )


    def test_03_vision_runs_only_after_analyze_button(self):
        button_marker = (
            '"문서 분석 시작 (Analyze Documents)"'
        )

        self.assertIn(button_marker, APP)

        button_index = APP.index(button_marker)
        vision_call = (
            "extract_pdf_page_with_vision("
        )

        self.assertIn(vision_call, APP)

        vision_index = APP.index(vision_call)

        self.assertGreater(
            vision_index,
            button_index,
            "Vision must not run during ordinary PDF upload/rerun.",
        )


    def test_04_analyze_path_prepares_pdf_before_semantic_analysis(self):
        prepare_call = (
            "prepare_pdf_document_for_semantic_analysis("
        )
        semantic_call = "analyze_semantic_documents("

        self.assertIn(prepare_call, APP)
        self.assertIn(semantic_call, APP)

        self.assertLess(
            APP.index(prepare_call),
            APP.index(semantic_call),
            "Vision recovery must happen before semantic analysis.",
        )


if __name__ == "__main__":
    unittest.main()
