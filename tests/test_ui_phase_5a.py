import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class UiPhase5ATest(unittest.TestCase):
    APP_PATH = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ui"
        / "app.py"
    )

    def test_01_judge_facing_pdf_upload_is_default(self):
        app = AppTest.from_file(
            str(self.APP_PATH),
            default_timeout=20,
        ).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            app.radio[0].value,
            "PDF Upload",
        )
        self.assertEqual(
            len(app.get("file_uploader")),
            3,
        )
        self.assertEqual(
            [button.label for button in app.button],
            ["문서 분석 시작 (Analyze Documents)"],
        )

    def test_02_original_text_input_path_remains_available(self):
        app = AppTest.from_file(
            str(self.APP_PATH),
            default_timeout=20,
        ).run()
        app.radio[0].set_value(
            "Text Input"
        ).run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(
            [item.label for item in app.text_area],
            [
                "Requirement document text",
                "Verification document text",
            ],
        )


if __name__ == "__main__":
    unittest.main()
