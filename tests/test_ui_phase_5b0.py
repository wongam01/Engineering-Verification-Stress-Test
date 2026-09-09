import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


class UiPhase5B0Test(unittest.TestCase):
    APP_PATH = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ui"
        / "app.py"
    )

    def test_01_korean_first_four_stage_shell_is_present(self):
        source = self.APP_PATH.read_text()

        for label in (
            "1 · 문서 입력 (Documents)",
            "2 · 공학 데이터 추출 (Engineering Extraction)",
            "3 · 검증 모델 및 검토 (Verification Model & Review)",
            "4 · 검증 결과 (Verification Result)",
        ):
            self.assertIn(label, source)

        for old_label in (
            "4 · Prepared Formal Model",
            "5 · Formal Human Review",
            "6 · Verification Result",
        ):
            self.assertNotIn(old_label, source)

        self.assertIn(
            "Deterministic Solver",
            source,
        )
        self.assertIn(
            "Source Provenance",
            source,
        )

    def test_02_pdf_first_runtime_path_is_preserved(self):
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


    def test_03_judge_facing_result_language_is_present(self):
        source = self.APP_PATH.read_text()

        for label in (
            "검증 이탈 발견 (Verification Escape Found)",
            "반례 (Counterexample)",
            "반례 값 (Counterexample)",
            "요구조건 위반량 (Violation)",
            "현실 가능 범위 (Feasible Domain) · PASS",
            "검사 기준 (Verification Criterion) · PASS",
            "설계 요구조건 (Requirement) · FAIL",
            "검증 격차 분류 (Gap Classification)",
        ):
            self.assertIn(label, source)

        self.assertNotIn(
            '"VERIFICATION ESCAPE DETECTED"',
            source,
        )

        self.assertIn(
            "Deterministic Solver",
            source,
        )

        self.assertIn(
            "F(x) ∧ V(x) ∧ ¬R(x)",
            source,
        )


    def test_04_technical_metadata_is_moved_to_advanced(self):
        source = self.APP_PATH.read_text()

        for label in (
            "문서 세부정보 (Advanced)",
            "원문 추적 정보 (Advanced)",
            "추적 세부정보 (Advanced)",
            "고급 정보 (Advanced) · Assurance Report",
            "고급 정보 (Advanced) · Raw Verification Data",
        ):
            self.assertIn(label, source)

    def test_05_verification_pipeline_depth_is_visible(self):
        source = self.APP_PATH.read_text()

        for label in (
            "검증 파이프라인 상태",
            "Source Provenance",
            "Semantic Review",
            "Variable Mapping",
            "Feasible Domain Evidence",
            "Formal Human Review",
            "Deterministic Solver",
        ):
            self.assertIn(label, source)

    def test_06_evidence_and_gap_are_judge_facing(self):
        source = self.APP_PATH.read_text()

        for label in (
            "근거 문서 (Evidence Trace)",
            "원문 근거",
            "검증 격차 분류 (Gap Classification)",
            "허용 경계 누락",
            "관계형 허용 경계 격차",
            "검증 범위 누락",
        ):
            self.assertIn(label, source)


    def test_07_visual_polish_preserves_engineering_depth(self):
        source = self.APP_PATH.read_text()

        for label in (
            "검증 모델 요약 (Engineering Model Summary)",
            "세부 검토 항목 (Exact Review Targets)",
            "허용 상한 초과 ",
            "분류 근거 원문 (Advanced)",
            "원본 PDF 페이지 보기",
            "엔지니어 입력 운영 근거",
            "현재 Phase 5B-0에서는 F가 PDF에서 자동",
        ):
            self.assertIn(label, source)

        self.assertIn(
            "if len(state_rows) > 1",
            source,
        )

        self.assertIn(
            "gap_explanation_ko",
            source,
        )


if __name__ == "__main__":
    unittest.main()
