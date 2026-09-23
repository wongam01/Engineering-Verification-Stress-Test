import unittest
from types import SimpleNamespace

from src.application.pdf_ingress import (
    pdf_document_should_attempt_automatic_vision,
    pdf_document_vision_candidate_page_numbers,
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
):
    return SimpleNamespace(
        pages=tuple(pages),
        raw_bytes=b"%PDF-test",
        total_pages=len(pages),
        status=status,
    )


class PdfIngressVisionPolicyTest(unittest.TestCase):
    def test_candidate_pages_are_detected_without_ai(self):
        doc = document(
            pages=[
                page(1, "usable"),
                page(2, ""),
                page(3, "   "),
                page(4, "usable"),
            ],
            status="READY_FOR_SEMANTIC_ANALYSIS",
        )

        self.assertEqual(
            pdf_document_vision_candidate_page_numbers(
                doc
            ),
            (2, 3),
        )

    def test_small_missing_page_set_can_use_automatic_vision(self):
        doc = document(
            pages=[
                page(1, ""),
                page(2, ""),
                page(3, "usable"),
            ],
            status="READY_FOR_SEMANTIC_ANALYSIS",
        )

        self.assertTrue(
            pdf_document_should_attempt_automatic_vision(
                doc
            )
        )

    def test_partial_text_over_budget_does_not_auto_vision(self):
        pages = [
            page(index, "")
            for index in range(1, 14)
        ]
        pages.append(
            page(14, "usable embedded text")
        )

        doc = document(
            pages=pages,
            status="READY_FOR_SEMANTIC_ANALYSIS",
        )

        self.assertFalse(
            pdf_document_should_attempt_automatic_vision(
                doc
            )
        )

    def test_image_only_over_budget_does_not_auto_vision(self):
        doc = document(
            pages=[
                page(index, "")
                for index in range(1, 23)
            ],
            status=(
                "IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED"
            ),
        )

        self.assertFalse(
            pdf_document_should_attempt_automatic_vision(
                doc
            )
        )

    def test_image_only_within_budget_can_use_vision(self):
        doc = document(
            pages=[
                page(index, "")
                for index in range(1, 6)
            ],
            status=(
                "IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED"
            ),
        )

        self.assertTrue(
            pdf_document_should_attempt_automatic_vision(
                doc
            )
        )


if __name__ == "__main__":
    unittest.main()
