from io import BytesIO
import unittest

from pypdf import PdfWriter

from src.application.pdf_ingress import (
    ingest_pdf_document,
)
from src.application.feasible_evidence_ingress import (
    analyze_feasible_evidence_pdf,
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


def fake_feasible_extractor(text, source_name):
    return [
        {
            "variable": "H",
            "source_text": "Observed hardness 58 to 60 HRC.",
            "source_line_id": "L1",
        }
    ]


class FeasibleEvidenceScopeProvenanceTest(unittest.TestCase):
    def test_01_selected_page_scope_survives_feasible_analysis(self):
        raw = build_blank_pdf(13)

        def fake_vision(pdf_bytes, page_number):
            if page_number == 2:
                return "Observed hardness 58 to 60 HRC."

            return f"Observed test evidence page {page_number}."

        document = ingest_pdf_document(
            role="feasible",
            filename="partial-evidence.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=(2, 11),
        )

        analysis = analyze_feasible_evidence_pdf(
            document,
            extractor=fake_feasible_extractor,
        )

        self.assertEqual(
            analysis.analysis_scope,
            "SELECTED_PAGES",
        )

        self.assertEqual(
            analysis.vision_processed_page_numbers,
            (2, 11),
        )

        self.assertEqual(
            analysis.vision_unprocessed_candidate_page_numbers,
            (
                1, 3, 4, 5, 6, 7,
                8, 9, 10, 12, 13,
            ),
        )

        self.assertFalse(
            analysis.full_document_coverage
        )

    def test_02_full_vision_coverage_is_marked_full_document(self):
        raw = build_blank_pdf(12)

        def fake_vision(pdf_bytes, page_number):
            if page_number == 2:
                return "Observed hardness 58 to 60 HRC."

            return f"Observed evidence page {page_number}."

        document = ingest_pdf_document(
            role="feasible",
            filename="full-evidence.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=tuple(range(1, 13)),
        )

        analysis = analyze_feasible_evidence_pdf(
            document,
            extractor=fake_feasible_extractor,
        )

        self.assertEqual(
            analysis.analysis_scope,
            "FULL_DOCUMENT",
        )

        self.assertEqual(
            analysis.vision_processed_page_numbers,
            tuple(range(1, 13)),
        )

        self.assertEqual(
            analysis.vision_unprocessed_candidate_page_numbers,
            (),
        )

        self.assertTrue(
            analysis.full_document_coverage
        )

    def test_03_not_ready_document_is_not_misrepresented_as_full_analysis(self):
        raw = build_blank_pdf(13)

        document = ingest_pdf_document(
            role="feasible",
            filename="unprocessed-scan.pdf",
            content=raw,
        )

        analysis = analyze_feasible_evidence_pdf(
            document,
            extractor=fake_feasible_extractor,
        )

        self.assertEqual(
            analysis.status,
            "FEASIBLE_DOCUMENT_NOT_READY",
        )

        self.assertEqual(
            analysis.analysis_scope,
            "NOT_ANALYZED",
        )

        self.assertFalse(
            analysis.full_document_coverage
        )


if __name__ == "__main__":
    unittest.main()
