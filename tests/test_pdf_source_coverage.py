import unittest
from types import SimpleNamespace

from src.application.pdf_ingress import (
    pdf_document_source_coverage_status,
)


def page(number, text):
    return SimpleNamespace(
        page_number=number,
        text=text,
    )


def document(
    *,
    pages,
    status,
    ready,
):
    return SimpleNamespace(
        pages=tuple(pages),
        raw_bytes=b"%PDF-test",
        total_pages=len(pages),
        status=status,
        ready_for_semantic_analysis=ready,
    )


class PdfSourceCoverageTest(unittest.TestCase):
    def test_text_ready(self):
        doc = document(
            pages=[
                page(1, "text"),
                page(2, "text"),
            ],
            status="READY_FOR_SEMANTIC_ANALYSIS",
            ready=True,
        )

        self.assertEqual(
            pdf_document_source_coverage_status(
                doc
            ),
            "TEXT_READY",
        )

    def test_small_gap_uses_auto_vision(self):
        doc = document(
            pages=[
                page(1, ""),
                page(2, "text"),
            ],
            status="READY_FOR_SEMANTIC_ANALYSIS",
            ready=True,
        )

        self.assertEqual(
            pdf_document_source_coverage_status(
                doc
            ),
            "AUTO_VISION",
        )

    def test_mixed_pdf_over_budget_is_partial_text(self):
        pages = [
            page(index, "")
            for index in range(1, 14)
        ]
        pages.append(
            page(14, "embedded text")
        )

        doc = document(
            pages=pages,
            status="READY_FOR_SEMANTIC_ANALYSIS",
            ready=True,
        )

        self.assertEqual(
            pdf_document_source_coverage_status(
                doc
            ),
            "PARTIAL_TEXT",
        )

    def test_image_only_over_budget_is_deferred(self):
        doc = document(
            pages=[
                page(index, "")
                for index in range(1, 23)
            ],
            status=(
                "IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED"
            ),
            ready=False,
        )

        self.assertEqual(
            pdf_document_source_coverage_status(
                doc
            ),
            "VISION_DEFERRED",
        )

    def test_structurally_unsupported_source_is_blocked(self):
        doc = document(
            pages=[],
            status="INVALID_PDF",
            ready=False,
        )

        self.assertEqual(
            pdf_document_source_coverage_status(
                doc
            ),
            "BLOCKED",
        )


if __name__ == "__main__":
    unittest.main()
