import unittest
from unittest.mock import patch

from src.application.pdf_ingress import (
    DEFAULT_MAX_DEEP_VISION_PAGES,
    IngestedPdfDocument,
    PdfPageText,
    prepare_pdf_document_with_deep_vision,
    rebind_pdf_document_role,
)


def page(number, text):
    return PdfPageText(
        page_number=number,
        text=text,
        text_sha256=str(number),
    )


def document(
    *,
    role="requirement",
    page_count=3,
    text_pages=(),
    status="READY_FOR_SEMANTIC_ANALYSIS",
):
    pages = tuple(
        page(
            number,
            "embedded text"
            if number in text_pages
            else "",
        )
        for number in range(1, page_count + 1)
    )

    return IngestedPdfDocument(
        role=role,
        filename="source.pdf",
        content_sha256="abc123",
        raw_bytes=b"%PDF-test",
        total_pages=page_count,
        pages=pages,
        status=status,
    )


class PdfDeepVisionTest(unittest.TestCase):
    def test_rebind_changes_only_role(self):
        original = document(
            role="requirement",
            page_count=2,
            text_pages=(1,),
        )

        rebound = rebind_pdf_document_role(
            original,
            "verification",
        )

        self.assertEqual(
            rebound.role,
            "verification",
        )
        self.assertEqual(
            rebound.content_sha256,
            original.content_sha256,
        )
        self.assertEqual(
            rebound.pages,
            original.pages,
        )
        self.assertEqual(
            rebound.raw_bytes,
            original.raw_bytes,
        )

    def test_invalid_role_is_rejected(self):
        original = document()

        with self.assertRaises(ValueError):
            rebind_pdf_document_role(
                original,
                "unknown",
            )

    def test_deep_vision_passes_all_missing_pages_explicitly(self):
        original = document(
            page_count=22,
            text_pages=(),
            status=(
                "IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED"
            ),
        )

        prepared = document(
            page_count=22,
            text_pages=tuple(range(1, 23)),
        )

        with patch(
            "src.application.pdf_ingress.ingest_pdf_document",
            return_value=prepared,
        ) as ingest:
            result = prepare_pdf_document_with_deep_vision(
                original,
                vision_page_extractor=lambda *_: "text",
            )

        self.assertIs(
            result,
            prepared,
        )

        kwargs = ingest.call_args.kwargs

        self.assertEqual(
            kwargs["vision_page_numbers"],
            tuple(range(1, 23)),
        )
        self.assertEqual(
            kwargs["max_vision_pages"],
            DEFAULT_MAX_DEEP_VISION_PAGES,
        )

    def test_deep_vision_uses_only_missing_pages(self):
        original = document(
            page_count=5,
            text_pages=(1, 3, 5),
        )

        with patch(
            "src.application.pdf_ingress.ingest_pdf_document",
            return_value=original,
        ) as ingest:
            prepare_pdf_document_with_deep_vision(
                original,
                vision_page_extractor=lambda *_: "text",
            )

        self.assertEqual(
            ingest.call_args.kwargs[
                "vision_page_numbers"
            ],
            (2, 4),
        )

    def test_complete_document_does_not_reingest(self):
        original = document(
            page_count=3,
            text_pages=(1, 2, 3),
        )

        with patch(
            "src.application.pdf_ingress.ingest_pdf_document",
        ) as ingest:
            result = prepare_pdf_document_with_deep_vision(
                original,
                vision_page_extractor=lambda *_: "text",
            )

        self.assertIs(
            result,
            original,
        )
        ingest.assert_not_called()


if __name__ == "__main__":
    unittest.main()
