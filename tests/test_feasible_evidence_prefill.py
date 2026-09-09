from hashlib import sha256
import unittest

from src.application.feasible_evidence_ingress import (
    analyze_feasible_evidence_pdf,
    build_feasible_evidence_prefills,
    confirm_ambiguous_feasible_source_location,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
    PdfPageText,
)


SOURCE = (
    "Measured production hardness H "
    "ranged from 58 to 60 HRC."
)


def document(
    pages=None,
):
    page_texts = (
        pages
        if pages is not None
        else [SOURCE]
    )

    raw = b"%PDF-prefill"

    return IngestedPdfDocument(
        role="feasible",
        filename="Operating_Evidence.pdf",
        content_sha256=sha256(
            raw
        ).hexdigest(),
        raw_bytes=raw,
        total_pages=len(
            page_texts
        ),
        pages=tuple(
            PdfPageText(
                page_number=index,
                text=text,
                text_sha256=sha256(
                    text.encode(
                        "utf-8"
                    )
                ).hexdigest(),
            )
            for index, text
            in enumerate(
                page_texts,
                start=1,
            )
        ),
        status=(
            "READY_FOR_SEMANTIC_ANALYSIS"
        ),
        issues=(),
    )


def extractor(
    text,
    source_name,
):
    return [
        {
            "source_line_id": "L1",
            "variable": "H",
            "min": "58",
            "max": "60",
            "unit": "HRC",
            "evidence_type":
                "observed_test_data",
            "needs_review": False,
            "review_reason": None,
            "source_text": SOURCE,
        }
    ]


class FeasibleEvidencePrefillTest(
    unittest.TestCase
):
    def build_analysis(
        self,
        pages=None,
    ):
        return (
            analyze_feasible_evidence_pdf(
                document(
                    pages
                ),
                extractor=extractor,
            )
        )

    def test_01_no_engineer_approval_blocks_prefill(self):
        analysis = (
            self.build_analysis()
        )

        result = (
            build_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=[],
                canonical_variable_by_candidate={},
            )
        )

        self.assertFalse(
            result.ready
        )
        self.assertEqual(
            result.status,
            "FEASIBLE_PREFILL_REVIEW_REQUIRED",
        )

    def test_02_unknown_approval_fails_safe(self):
        analysis = (
            self.build_analysis()
        )

        result = (
            build_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=[
                    "unknown"
                ],
                canonical_variable_by_candidate={},
            )
        )

        self.assertEqual(
            result.status,
            "INVALID_FEASIBLE_APPROVAL",
        )

    def test_03_missing_canonical_mapping_blocks(self):
        analysis = (
            self.build_analysis()
        )

        candidate = (
            analysis.candidates[0]
        )

        result = (
            build_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=[
                    candidate.candidate_id
                ],
                canonical_variable_by_candidate={},
            )
        )

        self.assertFalse(
            result.ready
        )
        self.assertIn(
            "Canonical variable",
            result.issues[0],
        )

    def test_04_approved_candidate_builds_exact_prefill(self):
        analysis = (
            self.build_analysis()
        )

        candidate = (
            analysis.candidates[0]
        )

        result = (
            build_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=[
                    candidate.candidate_id
                ],
                canonical_variable_by_candidate={
                    candidate.candidate_id:
                        "H",
                },
            )
        )

        self.assertTrue(
            result.ready
        )

        prefill = (
            result.prefills[0]
        )

        self.assertEqual(
            prefill.source_variable,
            "H",
        )
        self.assertEqual(
            prefill.canonical_variable,
            "H",
        )
        self.assertEqual(
            prefill.feasible_min,
            "58",
        )
        self.assertEqual(
            prefill.feasible_max,
            "60",
        )
        self.assertEqual(
            prefill.unit,
            "HRC",
        )
        self.assertEqual(
            prefill.evidence_type,
            "observed_test_data",
        )
        self.assertEqual(
            prefill.evidence_reference,
            "Operating_Evidence.pdf:p1:L1",
        )
        self.assertEqual(
            prefill.source_sha256,
            analysis.source_sha256,
        )

    def test_05_ambiguous_source_blocks_prefill(self):
        analysis = (
            self.build_analysis(
                [
                    SOURCE,
                    SOURCE,
                ]
            )
        )

        candidate = (
            analysis.candidates[0]
        )

        result = (
            build_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=[
                    candidate.candidate_id
                ],
                canonical_variable_by_candidate={
                    candidate.candidate_id:
                        "H",
                },
            )
        )

        self.assertFalse(
            result.ready
        )
        self.assertIn(
            "Source location",
            result.issues[0],
        )

    def test_06_human_page_confirmation_allows_prefill(self):
        analysis = (
            self.build_analysis(
                [
                    SOURCE,
                    SOURCE,
                ]
            )
        )

        candidate = (
            analysis.candidates[0]
        )

        confirmed = (
            confirm_ambiguous_feasible_source_location(
                candidate,
                selected_page=2,
                confirmed=True,
            )
        )

        analysis.candidates[0] = (
            confirmed
        )

        result = (
            build_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=[
                    confirmed.candidate_id
                ],
                canonical_variable_by_candidate={
                    confirmed.candidate_id:
                        "H",
                },
            )
        )

        self.assertTrue(
            result.ready
        )
        self.assertEqual(
            result.prefills[0]
            .evidence_reference,
            "Operating_Evidence.pdf:p2:L1",
        )

    def test_07_ai_review_required_cannot_be_promoted(self):
        analysis = (
            self.build_analysis()
        )

        candidate = (
            analysis.candidates[0]
        )

        candidate.extraction[
            "needs_review"
        ] = True

        candidate.extraction[
            "review_reason"
        ] = "Evidence meaning is ambiguous."

        result = (
            build_feasible_evidence_prefills(
                analysis,
                approved_candidate_ids=[
                    candidate.candidate_id
                ],
                canonical_variable_by_candidate={
                    candidate.candidate_id:
                        "H",
                },
            )
        )

        self.assertFalse(
            result.ready
        )
        self.assertIn(
            "requires review",
            result.issues[0],
        )


if __name__ == "__main__":
    unittest.main()
