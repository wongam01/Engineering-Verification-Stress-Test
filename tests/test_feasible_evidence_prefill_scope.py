from io import BytesIO
import unittest

from pypdf import PdfWriter

from src.application.pdf_ingress import (
    ingest_pdf_document,
)
from src.application.feasible_evidence_ingress import (
    analyze_feasible_evidence_pdf,
    build_feasible_evidence_prefills,
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


def fake_extractor(text, source_name):
    return [
        {
            "variable": "H",
            "min": "58",
            "max": "60",
            "unit": "HRC",
            "evidence_type": "observed_test_data",
            "source_text": "Observed hardness 58 to 60 HRC.",
            "source_line_id": "L1",
            "needs_review": False,
            "review_reason": "",
        }
    ]


class FeasibleEvidencePrefillScopeTest(unittest.TestCase):
    def test_01_selected_scope_survives_into_prefill_result_and_prefill(self):
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
            extractor=fake_extractor,
        )

        candidate = analysis.candidates[0]

        result = build_feasible_evidence_prefills(
            analysis,
            approved_candidate_ids=[
                candidate.candidate_id,
            ],
            canonical_variable_by_candidate={
                candidate.candidate_id: "H",
            },
        )

        self.assertTrue(result.ready)

        self.assertEqual(
            result.analysis_scope,
            "SELECTED_PAGES",
        )
        self.assertFalse(
            result.full_document_coverage
        )
        self.assertEqual(
            result.vision_processed_page_numbers,
            (2, 11),
        )
        self.assertEqual(
            result.vision_unprocessed_candidate_page_numbers,
            (
                1, 3, 4, 5, 6, 7,
                8, 9, 10, 12, 13,
            ),
        )

        prefill = result.prefills[0]

        self.assertEqual(
            prefill.analysis_scope,
            "SELECTED_PAGES",
        )
        self.assertFalse(
            prefill.full_document_coverage
        )
        self.assertEqual(
            prefill.vision_processed_page_numbers,
            (2, 11),
        )
        self.assertEqual(
            prefill.vision_unprocessed_candidate_page_numbers,
            (
                1, 3, 4, 5, 6, 7,
                8, 9, 10, 12, 13,
            ),
        )

    def test_02_full_scope_remains_full_through_prefill(self):
        raw = build_blank_pdf(12)

        def fake_vision(pdf_bytes, page_number):
            if page_number == 2:
                return "Observed hardness 58 to 60 HRC."

            return f"Observed test evidence page {page_number}."

        document = ingest_pdf_document(
            role="feasible",
            filename="full-evidence.pdf",
            content=raw,
            vision_page_extractor=fake_vision,
            vision_page_numbers=tuple(range(1, 13)),
        )

        analysis = analyze_feasible_evidence_pdf(
            document,
            extractor=fake_extractor,
        )

        candidate = analysis.candidates[0]

        result = build_feasible_evidence_prefills(
            analysis,
            approved_candidate_ids=[
                candidate.candidate_id,
            ],
            canonical_variable_by_candidate={
                candidate.candidate_id: "H",
            },
        )

        self.assertEqual(
            result.analysis_scope,
            "FULL_DOCUMENT",
        )
        self.assertTrue(
            result.full_document_coverage
        )

        prefill = result.prefills[0]

        self.assertEqual(
            prefill.analysis_scope,
            "FULL_DOCUMENT",
        )
        self.assertTrue(
            prefill.full_document_coverage
        )

    def test_03_failed_prefill_result_still_preserves_analysis_scope(self):
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
            extractor=fake_extractor,
        )

        result = build_feasible_evidence_prefills(
            analysis,
            approved_candidate_ids=[
                "unknown-candidate",
            ],
            canonical_variable_by_candidate={},
        )

        self.assertFalse(result.ready)
        self.assertEqual(
            result.analysis_scope,
            "SELECTED_PAGES",
        )
        self.assertFalse(
            result.full_document_coverage
        )
        self.assertEqual(
            result.vision_processed_page_numbers,
            (2, 11),
        )


if __name__ == "__main__":
    unittest.main()
