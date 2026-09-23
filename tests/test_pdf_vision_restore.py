import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.application.pdf_ingress import (
    IngestedPdfDocument,
    PdfPageText,
)
from src.application.pdf_vision_restore import (
    restore_pdf_document_from_vision_cache,
)


def document():
    return IngestedPdfDocument(
        role="requirement",
        filename="source.pdf",
        content_sha256="sha",
        raw_bytes=b"%PDF-test",
        total_pages=2,
        pages=(
            PdfPageText(
                page_number=1,
                text="embedded",
                text_sha256="1",
            ),
            PdfPageText(
                page_number=2,
                text="",
                text_sha256="2",
            ),
        ),
        status="READY_FOR_SELECTED_PAGE_ANALYSIS",
    )


class PdfVisionRestoreTest(unittest.TestCase):
    def test_complete_text_document_returns_unchanged(self):
        original = IngestedPdfDocument(
            role="requirement",
            filename="text.pdf",
            content_sha256="text-sha",
            raw_bytes=b"%PDF-text",
            total_pages=1,
            pages=(
                PdfPageText(
                    page_number=1,
                    text="text",
                    text_sha256="1",
                ),
            ),
            status="READY_FOR_SEMANTIC_ANALYSIS",
        )

        result = restore_pdf_document_from_vision_cache(
            original
        )

        self.assertIs(
            result,
            original,
        )

    def test_bundle_fast_path_is_used(self):
        original = document()

        restored = IngestedPdfDocument(
            role="requirement",
            filename="source.pdf",
            content_sha256="sha",
            raw_bytes=b"%PDF-test",
            total_pages=2,
            pages=(
                PdfPageText(
                    page_number=1,
                    text="embedded",
                    text_sha256="1",
                ),
                PdfPageText(
                    page_number=2,
                    text="vision",
                    text_sha256="2",
                ),
            ),
            status="READY_FOR_SEMANTIC_ANALYSIS",
        )

        with patch(
            "src.application.pdf_vision_restore."
            "load_pdf_vision_transcription_bundle",
            return_value={2: "vision"},
        ), patch(
            "src.application.pdf_vision_restore."
            "prepare_pdf_document_with_deep_vision",
            return_value=restored,
        ) as prepare, patch(
            "src.application.pdf_vision_restore."
            "is_pdf_page_vision_cached",
            side_effect=AssertionError(
                "page-level cache should not be checked"
            ),
        ):
            result = restore_pdf_document_from_vision_cache(
                original
            )

        self.assertIs(
            result,
            restored,
        )
        self.assertEqual(
            prepare.call_count,
            1,
        )

    def test_missing_bundle_and_incomplete_page_cache_is_safe(self):
        original = document()

        with patch(
            "src.application.pdf_vision_restore."
            "load_pdf_vision_transcription_bundle",
            return_value=None,
        ), patch(
            "src.application.pdf_vision_restore."
            "is_pdf_page_vision_cached",
            return_value=False,
        ):
            result = restore_pdf_document_from_vision_cache(
                original
            )

        self.assertIs(
            result,
            original,
        )


if __name__ == "__main__":
    unittest.main()
