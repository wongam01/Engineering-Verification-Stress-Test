from io import BytesIO
import unittest

from pypdf import PdfWriter

from src.application.pdf_ingress import (
    build_semantic_document,
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


class PdfSemanticScopeProvenanceTest(unittest.TestCase):
    def test_01_selected_page_scope_survives_semantic_conversion(self):
        raw = build_blank_pdf(13)

        def fake_vision(pdf_bytes, page_number):
            return f"Selected page {page_number}"

        document = ingest_pdf_document(
            role="requirement",
            filename="partial-scan.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=(2, 11),
        )

        semantic = build_semantic_document(
            document
        )

        self.assertEqual(
            semantic.analysis_scope,
            "SELECTED_PAGES",
        )
        self.assertEqual(
            semantic.vision_processed_page_numbers,
            (2, 11),
        )
        self.assertEqual(
            semantic.vision_unprocessed_candidate_page_numbers,
            (
                1, 3, 4, 5, 6, 7,
                8, 9, 10, 12, 13,
            ),
        )


    def test_02_full_scope_remains_full_document(self):
        raw = build_blank_pdf(12)

        def fake_vision(pdf_bytes, page_number):
            return f"Page {page_number}"

        document = ingest_pdf_document(
            role="verification",
            filename="full-scan.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=tuple(range(1, 13)),
        )

        semantic = build_semantic_document(
            document
        )

        self.assertEqual(
            semantic.analysis_scope,
            "FULL_DOCUMENT",
        )
        self.assertEqual(
            semantic.vision_processed_page_numbers,
            tuple(range(1, 13)),
        )
        self.assertEqual(
            semantic.vision_unprocessed_candidate_page_numbers,
            (),
        )


    def test_03_regular_text_pdf_defaults_to_full_document_scope(self):
        from src.application.semantic_ingress import (
            SemanticDocument,
        )

        semantic = SemanticDocument(
            role="requirement",
            source_name="plain.txt",
            text="Pressure shall not exceed 10 bar.",
        )

        self.assertEqual(
            semantic.analysis_scope,
            "FULL_DOCUMENT",
        )
        self.assertEqual(
            semantic.vision_processed_page_numbers,
            (),
        )
        self.assertEqual(
            semantic.vision_unprocessed_candidate_page_numbers,
            (),
        )


if __name__ == "__main__":
    unittest.main()
