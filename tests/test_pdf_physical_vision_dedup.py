import unittest
from unittest.mock import patch

from src.application.pdf_ingress import (
    IngestedPdfDocument,
    PdfPageText,
    prepare_pdf_document_views_with_vision,
    rebind_pdf_document_role,
)


def document(role, sha="same-sha"):
    return IngestedPdfDocument(
        role=role,
        filename="same.pdf",
        content_sha256=sha,
        raw_bytes=b"%PDF-test",
        total_pages=2,
        pages=(
            PdfPageText(
                page_number=1,
                text="",
                text_sha256="1",
            ),
            PdfPageText(
                page_number=2,
                text="",
                text_sha256="2",
            ),
        ),
        status="IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED",
    )


class PhysicalVisionDedupTest(unittest.TestCase):
    def test_deep_vision_runs_once_for_three_role_views(self):
        documents = (
            document("requirement"),
            document("verification"),
            document("feasible"),
        )

        prepared = rebind_pdf_document_role(
            documents[0],
            "requirement",
        )

        with patch(
            "src.application.pdf_ingress."
            "prepare_pdf_document_with_deep_vision",
            return_value=prepared,
        ) as deep_prepare:
            result = prepare_pdf_document_views_with_vision(
                documents,
                vision_page_extractor=lambda *_: "text",
                deep_vision=True,
            )

        self.assertEqual(
            deep_prepare.call_count,
            1,
        )

        self.assertEqual(
            tuple(item.role for item in result),
            (
                "requirement",
                "verification",
                "feasible",
            ),
        )

        self.assertTrue(
            all(
                item.content_sha256 == "same-sha"
                for item in result
            )
        )

    def test_two_physical_sources_prepare_twice(self):
        documents = (
            document(
                "requirement",
                sha="sha-a",
            ),
            document(
                "verification",
                sha="sha-a",
            ),
            document(
                "requirement",
                sha="sha-b",
            ),
            document(
                "feasible",
                sha="sha-b",
            ),
        )

        with patch(
            "src.application.pdf_ingress."
            "prepare_pdf_document_with_deep_vision",
            side_effect=lambda document, **_: document,
        ) as deep_prepare:
            prepare_pdf_document_views_with_vision(
                documents,
                vision_page_extractor=lambda *_: "text",
                deep_vision=True,
            )

        self.assertEqual(
            deep_prepare.call_count,
            2,
        )


if __name__ == "__main__":
    unittest.main()
