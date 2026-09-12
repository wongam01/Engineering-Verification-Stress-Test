from io import BytesIO
import unittest

from pypdf import PdfWriter

import src.application.pdf_ingress as pdf_ingress
from src.application.pdf_ingress import (
    ingest_pdf_document,
    prepare_pdf_document_for_semantic_analysis,
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


class PdfVisionBudgetTest(unittest.TestCase):
    def test_01_default_pdf_size_limit_is_50_mib(self):
        self.assertEqual(
            pdf_ingress.DEFAULT_MAX_PDF_BYTES,
            50 * 1024 * 1024,
        )


    def test_02_default_auto_vision_budget_is_12_pages(self):
        self.assertEqual(
            getattr(
                pdf_ingress,
                "DEFAULT_MAX_VISION_PAGES",
                None,
            ),
            12,
        )


    def test_03_exactly_12_vision_pages_are_allowed(self):
        raw = build_blank_pdf(12)
        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return f"Vision page {page_number}"

        document = ingest_pdf_document(
            role="requirement",
            filename="twelve-pages.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
        )

        self.assertTrue(
            document.ready_for_semantic_analysis
        )
        self.assertEqual(
            calls,
            list(range(1, 13)),
        )


    def test_04_13_vision_pages_fail_before_any_api_call(self):
        raw = build_blank_pdf(13)
        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return f"Vision page {page_number}"

        document = ingest_pdf_document(
            role="requirement",
            filename="thirteen-pages.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
        )

        self.assertFalse(
            document.ready_for_semantic_analysis
        )
        self.assertEqual(
            document.status,
            "VISION_PAGE_BUDGET_EXCEEDED",
        )

        self.assertEqual(
            calls,
            [],
            "Budget must be checked before any Vision call.",
        )

        issue_codes = {
            issue.code
            for issue in document.issues
        }

        self.assertIn(
            "PDF_VISION_PAGE_BUDGET_EXCEEDED",
            issue_codes,
        )


    def test_05_prepare_helper_also_blocks_before_api_calls(self):
        raw = build_blank_pdf(13)

        initial = ingest_pdf_document(
            role="verification",
            filename="large-scan.pdf",
            content=raw,
        )

        self.assertFalse(
            initial.ready_for_semantic_analysis
        )

        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return f"Vision page {page_number}"

        prepared = prepare_pdf_document_for_semantic_analysis(
            initial,
            vision_page_extractor=fake_vision,
        )

        self.assertFalse(
            prepared.ready_for_semantic_analysis
        )
        self.assertEqual(
            prepared.status,
            "VISION_PAGE_BUDGET_EXCEEDED",
        )
        self.assertEqual(
            calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
