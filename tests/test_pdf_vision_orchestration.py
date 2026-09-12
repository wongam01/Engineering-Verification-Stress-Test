from io import BytesIO
import unittest

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from src.application.pdf_ingress import (
    ingest_pdf_document,
    pdf_document_requires_vision,
    pdf_document_can_attempt_vision,
    prepare_pdf_document_for_semantic_analysis,
)


def build_pdf(page_texts):
    writer = PdfWriter()

    for text in page_texts:
        page = writer.add_blank_page(
            width=612,
            height=792,
        )

        if text is None:
            continue

        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_reference = writer._add_object(font)

        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): font_reference,
                    }
                )
            }
        )

        escaped = (
            str(text)
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

        stream = DecodedStreamObject()
        stream.set_data(
            (
                "BT /F1 12 Tf 72 720 Td ("
                + escaped
                + ") Tj ET"
            ).encode("latin-1")
        )

        page[NameObject("/Contents")] = writer._add_object(
            stream
        )

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class PdfVisionOrchestrationTest(unittest.TestCase):
    def test_01_text_only_document_does_not_require_vision(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="text.pdf",
            content=build_pdf(
                ["Ordinary embedded engineering text."]
            ),
        )

        self.assertTrue(document.ready_for_semantic_analysis)
        self.assertFalse(
            pdf_document_requires_vision(document)
        )
        self.assertTrue(
            pdf_document_can_attempt_vision(document)
        )

        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return "must not be called"

        prepared = prepare_pdf_document_for_semantic_analysis(
            document,
            vision_page_extractor=fake_vision,
        )

        self.assertIs(prepared, document)
        self.assertEqual(calls, [])


    def test_02_image_only_document_is_vision_recoverable(self):
        document = ingest_pdf_document(
            role="verification",
            filename="scan.pdf",
            content=build_pdf([None]),
        )

        self.assertFalse(document.ready_for_semantic_analysis)
        self.assertTrue(
            pdf_document_requires_vision(document)
        )
        self.assertTrue(
            pdf_document_can_attempt_vision(document)
        )

        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return "Scanned engineering criterion."

        prepared = prepare_pdf_document_for_semantic_analysis(
            document,
            vision_page_extractor=fake_vision,
        )

        self.assertTrue(
            prepared.ready_for_semantic_analysis
        )
        self.assertEqual(calls, [1])
        self.assertEqual(
            prepared.pages[0].text,
            "Scanned engineering criterion.",
        )


    def test_03_invalid_pdf_is_not_vision_recoverable(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="invalid.pdf",
            content=b"not a pdf",
        )

        self.assertFalse(
            pdf_document_requires_vision(document)
        )
        self.assertFalse(
            pdf_document_can_attempt_vision(document)
        )

        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return "must not be called"

        prepared = prepare_pdf_document_for_semantic_analysis(
            document,
            vision_page_extractor=fake_vision,
        )

        self.assertIs(prepared, document)
        self.assertEqual(calls, [])
        self.assertEqual(
            prepared.status,
            "INVALID_PDF",
        )


    def test_04_mixed_ready_document_still_requires_vision(self):
        document = ingest_pdf_document(
            role="feasible",
            filename="mixed.pdf",
            content=build_pdf(
                [
                    "Embedded page one.",
                    None,
                    "Embedded page three.",
                ]
            ),
        )

        # pypdf found some text, so the document is initially READY.
        self.assertTrue(document.ready_for_semantic_analysis)

        # But page 2 is still missing and must not be silently skipped.
        self.assertTrue(
            pdf_document_requires_vision(document)
        )
        self.assertTrue(
            pdf_document_can_attempt_vision(document)
        )

        calls = []

        def fake_vision(pdf_bytes, page_number):
            calls.append(page_number)
            return "Vision transcription for page two."

        prepared = prepare_pdf_document_for_semantic_analysis(
            document,
            vision_page_extractor=fake_vision,
        )

        self.assertTrue(
            prepared.ready_for_semantic_analysis
        )
        self.assertEqual(calls, [2])
        self.assertEqual(
            prepared.pages[1].text,
            "Vision transcription for page two.",
        )


if __name__ == "__main__":
    unittest.main()
