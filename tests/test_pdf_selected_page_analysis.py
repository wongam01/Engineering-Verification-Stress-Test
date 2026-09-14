from io import BytesIO
import unittest

from pypdf import PdfWriter

from src.application.pdf_ingress import (
    ingest_pdf_document,
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


class PdfSelectedPageAnalysisTest(unittest.TestCase):
    def test_01_partial_selection_has_distinct_ready_status(self):
        raw = build_blank_pdf(13)
        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return f"Selected page {page_number}"

        document = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=(2, 11),
        )

        self.assertEqual(
            calls,
            [2, 11],
        )
        self.assertEqual(
            document.status,
            "READY_FOR_SELECTED_PAGE_ANALYSIS",
        )
        self.assertTrue(
            document.ready_for_semantic_analysis
        )
        self.assertFalse(
            document.full_document_coverage
        )

    def test_02_scope_provenance_records_processed_and_unprocessed_pages(self):
        raw = build_blank_pdf(13)

        def fake_vision(pdf_bytes, page_number):
            return f"Selected page {page_number}"

        document = ingest_pdf_document(
            role="verification",
            filename="large-scan.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=(2, 11),
        )

        self.assertEqual(
            document.vision_processed_page_numbers,
            (2, 11),
        )

        self.assertEqual(
            document.vision_unprocessed_candidate_page_numbers,
            (
                1, 3, 4, 5, 6, 7,
                8, 9, 10, 12, 13,
            ),
        )

    def test_03_non_candidate_selection_fails_before_vision_call(self):
        raw = build_blank_pdf(13)
        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return "SHOULD NOT RUN"

        document = ingest_pdf_document(
            role="feasible",
            filename="large-scan.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=(1, 99),
        )

        self.assertFalse(
            document.ready_for_semantic_analysis
        )
        self.assertEqual(
            document.status,
            "VISION_PAGE_SELECTION_INVALID",
        )
        self.assertEqual(
            calls,
            [],
        )

    def test_04_selected_scope_cannot_exceed_budget(self):
        raw = build_blank_pdf(13)
        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return "SHOULD NOT RUN"

        document = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=tuple(range(1, 14)),
        )

        self.assertFalse(
            document.ready_for_semantic_analysis
        )
        self.assertEqual(
            document.status,
            "VISION_PAGE_SELECTION_INVALID",
        )
        self.assertEqual(
            calls,
            [],
        )

    def test_05_selected_page_must_produce_usable_text(self):
        raw = build_blank_pdf(13)

        def fake_vision(pdf_bytes, page_number):
            if page_number == 2:
                return "Usable selected page"

            return ""

        document = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=(2, 11),
        )

        self.assertFalse(
            document.ready_for_semantic_analysis
        )
        self.assertEqual(
            document.status,
            "VISION_SELECTED_PAGE_EXTRACTION_INCOMPLETE",
        )

    def test_06_complete_selection_remains_full_document_ready(self):
        raw = build_blank_pdf(12)
        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return f"Page {page_number}"

        document = ingest_pdf_document(
            role="requirement",
            filename="twelve-pages.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=tuple(range(1, 13)),
        )

        self.assertEqual(
            document.status,
            "READY_FOR_SEMANTIC_ANALYSIS",
        )
        self.assertTrue(
            document.ready_for_semantic_analysis
        )
        self.assertTrue(
            document.full_document_coverage
        )
        self.assertEqual(
            document.vision_unprocessed_candidate_page_numbers,
            (),
        )
        self.assertEqual(
            calls,
            list(range(1, 13)),
        )


if __name__ == "__main__":
    unittest.main()
