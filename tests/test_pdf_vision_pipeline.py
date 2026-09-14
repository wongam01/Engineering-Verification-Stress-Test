from io import BytesIO
import unittest

from pypdf import PdfWriter

from src.ai.pdf_page_triage import (
    PdfPageTriageResult,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
    PdfPageText,
    ingest_pdf_document,
)
from src.application.pdf_vision_pipeline import (
    prepare_pdf_document_with_page_triage,
)


def build_blank_pdf(page_count):
    writer = PdfWriter()

    for _ in range(page_count):
        writer.add_blank_page(
            width=612,
            height=792,
        )

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class PdfVisionPipelineTest(unittest.TestCase):
    def test_01_within_budget_skips_triage_and_processes_all_candidates(self):
        initial = ingest_pdf_document(
            role="requirement",
            filename="small-scan.pdf",
            content=build_blank_pdf(4),
        )

        triage_calls = []
        vision_calls = []

        def fake_triage(document, plan):
            triage_calls.append(
                plan.candidate_page_numbers
            )

            raise AssertionError(
                "Triage must not run within budget."
            )

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return f"Page {page_number}"

        result = prepare_pdf_document_with_page_triage(
            initial,
            vision_page_extractor=fake_vision,
            triage_recommender=fake_triage,
        )

        self.assertTrue(result.ready)
        self.assertEqual(
            result.status,
            "VISION_PREPARATION_READY",
        )
        self.assertEqual(
            triage_calls,
            [],
        )
        self.assertEqual(
            vision_calls,
            [1, 2, 3, 4],
        )
        self.assertEqual(
            result.selected_page_numbers,
            (1, 2, 3, 4),
        )
        self.assertTrue(
            result.document.full_document_coverage
        )

    def test_02_over_budget_uses_triage_then_selected_high_detail_pages(self):
        initial = ingest_pdf_document(
            role="feasible",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        triage_calls = []
        vision_calls = []

        def fake_triage(document, plan):
            triage_calls.append(
                plan.candidate_page_numbers
            )

            return PdfPageTriageResult(
                selected_page_numbers=(2, 11),
                reasons=(
                    (2, "measurement table"),
                    (11, "observed data"),
                ),
                summary="Two plausible evidence pages.",
            )

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return f"Selected page {page_number}"

        result = prepare_pdf_document_with_page_triage(
            initial,
            vision_page_extractor=fake_vision,
            triage_recommender=fake_triage,
        )

        self.assertTrue(result.ready)

        self.assertEqual(
            triage_calls,
            [tuple(range(1, 14))],
        )

        self.assertEqual(
            vision_calls,
            [2, 11],
        )

        self.assertEqual(
            result.selected_page_numbers,
            (2, 11),
        )

        self.assertEqual(
            result.document.status,
            "READY_FOR_SELECTED_PAGE_ANALYSIS",
        )

        self.assertFalse(
            result.document.full_document_coverage
        )

        self.assertEqual(
            result.document.vision_processed_page_numbers,
            (2, 11),
        )

        self.assertEqual(
            result.document.vision_unprocessed_candidate_page_numbers,
            (
                1, 3, 4, 5, 6, 7,
                8, 9, 10, 12, 13,
            ),
        )

    def test_03_invalid_triage_selection_is_blocked_before_high_detail_vision(self):
        initial = ingest_pdf_document(
            role="verification",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        vision_calls = []

        def fake_triage(document, plan):
            return PdfPageTriageResult(
                selected_page_numbers=(2, 99),
                reasons=(),
                summary="Invalid recommendation.",
            )

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return "SHOULD NOT RUN"

        result = prepare_pdf_document_with_page_triage(
            initial,
            vision_page_extractor=fake_vision,
            triage_recommender=fake_triage,
        )

        self.assertFalse(result.ready)
        self.assertEqual(
            result.status,
            "VISION_PREPARATION_BLOCKED",
        )
        self.assertEqual(
            vision_calls,
            [],
        )
        self.assertIn(
            "VISION_PAGE_SELECTION_NOT_CANDIDATE",
            result.issue_codes,
        )

    def test_04_over_budget_without_triage_is_fail_safe(self):
        initial = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        vision_calls = []

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return "SHOULD NOT RUN"

        result = prepare_pdf_document_with_page_triage(
            initial,
            vision_page_extractor=fake_vision,
            triage_recommender=None,
        )

        self.assertFalse(result.ready)
        self.assertEqual(
            result.status,
            "VISION_PREPARATION_BLOCKED",
        )
        self.assertEqual(
            vision_calls,
            [],
        )
        self.assertIn(
            "VISION_PAGE_SELECTION_REQUIRED",
            result.issue_codes,
        )

    def test_05_triage_exception_is_fail_safe(self):
        initial = ingest_pdf_document(
            role="feasible",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        vision_calls = []

        def fake_triage(document, plan):
            raise RuntimeError(
                "triage unavailable"
            )

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return "SHOULD NOT RUN"

        result = prepare_pdf_document_with_page_triage(
            initial,
            vision_page_extractor=fake_vision,
            triage_recommender=fake_triage,
        )

        self.assertFalse(result.ready)
        self.assertEqual(
            vision_calls,
            [],
        )
        self.assertIn(
            "VISION_PAGE_TRIAGE_FAILED",
            result.issue_codes,
        )

    def test_06_text_only_document_does_not_run_triage_or_vision(self):
        initial = IngestedPdfDocument(
            role="requirement",
            filename="text.pdf",
            content_sha256="test-sha256",
            raw_bytes=b"%PDF-test-fixture",
            total_pages=1,
            pages=(
                PdfPageText(
                    page_number=1,
                    text="Requirement text",
                    text_sha256="page-sha256",
                ),
            ),
            status="READY_FOR_SEMANTIC_ANALYSIS",
        )

        triage_calls = []
        vision_calls = []

        def fake_triage(document, plan):
            triage_calls.append(True)
            raise AssertionError(
                "Triage must not run."
            )

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            raise AssertionError(
                "Vision must not run."
            )

        result = prepare_pdf_document_with_page_triage(
            initial,
            vision_page_extractor=fake_vision,
            triage_recommender=fake_triage,
        )

        self.assertTrue(result.ready)
        self.assertEqual(
            result.status,
            "VISION_NOT_REQUIRED",
        )
        self.assertEqual(
            triage_calls,
            [],
        )
        self.assertEqual(
            vision_calls,
            [],
        )
        self.assertIs(
            result.document,
            initial,
        )

    def test_07_selected_page_extraction_failure_stays_blocked(self):
        initial = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        def fake_triage(document, plan):
            return PdfPageTriageResult(
                selected_page_numbers=(2, 11),
                reasons=(),
                summary="Selected pages.",
            )

        def fake_vision(pdf_bytes, page_number):
            if page_number == 2:
                return "Usable text"

            return ""

        result = prepare_pdf_document_with_page_triage(
            initial,
            vision_page_extractor=fake_vision,
            triage_recommender=fake_triage,
        )

        self.assertFalse(result.ready)

        self.assertEqual(
            result.document.status,
            "VISION_SELECTED_PAGE_EXTRACTION_INCOMPLETE",
        )

        self.assertIn(
            "PDF_VISION_SELECTED_PAGE_EXTRACTION_INCOMPLETE",
            result.issue_codes,
        )


if __name__ == "__main__":
    unittest.main()
