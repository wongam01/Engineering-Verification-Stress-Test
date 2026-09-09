from hashlib import sha256
import unittest

from src.application.feasible_evidence_ingress import (
    analyze_feasible_evidence_pdf,
    confirm_ambiguous_feasible_source_location,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
    PdfPageText,
)


def build_feasible_document(
    page_texts,
):
    raw = b"%PDF-feasible-fixture"

    pages = tuple(
        PdfPageText(
            page_number=index,
            text=text,
            text_sha256=sha256(
                text.encode("utf-8")
            ).hexdigest(),
        )
        for index, text in enumerate(
            page_texts,
            start=1,
        )
    )

    return IngestedPdfDocument(
        role="feasible",
        filename="Operating_Evidence.pdf",
        content_sha256=sha256(
            raw
        ).hexdigest(),
        raw_bytes=raw,
        total_pages=len(pages),
        pages=pages,
        status="READY_FOR_SEMANTIC_ANALYSIS",
        issues=(),
    )


def build_extractor(
    source_text,
    *,
    line_id="L1",
):
    def extractor(
        text,
        source_name,
    ):
        return [
            {
                "source_line_id":
                    line_id,
                "variable": "H",
                "min": "58",
                "max": "60",
                "unit": "HRC",
                "evidence_type":
                    "observed_test_data",
                "needs_review": False,
                "review_reason": None,
                "source_name":
                    "AI_SHOULD_NOT_CONTROL",
                "source_text":
                    source_text,
            }
        ]

    return extractor


class FeasibleEvidenceIngressTest(
    unittest.TestCase
):
    def test_01_unique_source_binds_exact_pdf_identity(self):
        source = (
            "Measured production hardness H "
            "ranged from 58 to 60 HRC."
        )

        document = build_feasible_document(
            [
                "Cover page",
                source,
            ]
        )

        result = (
            analyze_feasible_evidence_pdf(
                document,
                extractor=build_extractor(
                    source
                ),
            )
        )

        self.assertEqual(
            len(result.candidates),
            1,
        )

        candidate = (
            result.candidates[0]
        )

        self.assertEqual(
            candidate.source_name,
            "Operating_Evidence.pdf",
        )
        self.assertEqual(
            candidate.source_sha256,
            document.content_sha256,
        )
        self.assertEqual(
            candidate.source_block_id,
            "L1",
        )
        self.assertEqual(
            candidate.source_page,
            2,
        )
        self.assertEqual(
            candidate.source_pages,
            (2,),
        )
        self.assertEqual(
            candidate.source_location_status,
            "SOURCE_LOCATION_RESOLVED",
        )
        self.assertTrue(
            candidate.source_location_ready
        )
        self.assertFalse(
            candidate.approved
        )

    def test_02_repeated_source_is_ambiguous(self):
        source = (
            "Measured hardness H ranged "
            "from 58 to 60 HRC."
        )

        document = build_feasible_document(
            [
                source,
                source,
            ]
        )

        candidate = (
            analyze_feasible_evidence_pdf(
                document,
                extractor=build_extractor(
                    source
                ),
            )
            .candidates[0]
        )

        self.assertEqual(
            candidate.source_location_status,
            "SOURCE_LOCATION_AMBIGUOUS",
        )
        self.assertEqual(
            candidate.source_location_candidates,
            (1, 2),
        )
        self.assertFalse(
            candidate.source_location_ready
        )

    def test_03_ambiguous_page_confirmation_preserves_extraction(self):
        source = (
            "Measured hardness H ranged "
            "from 58 to 60 HRC."
        )

        document = build_feasible_document(
            [
                source,
                source,
            ]
        )

        candidate = (
            analyze_feasible_evidence_pdf(
                document,
                extractor=build_extractor(
                    source
                ),
            )
            .candidates[0]
        )

        original_extraction = dict(
            candidate.extraction
        )

        confirmed = (
            confirm_ambiguous_feasible_source_location(
                candidate,
                selected_page=2,
                confirmed=True,
            )
        )

        self.assertEqual(
            confirmed.source_location_status,
            "SOURCE_LOCATION_HUMAN_CONFIRMED",
        )
        self.assertEqual(
            confirmed.source_page,
            2,
        )
        self.assertEqual(
            confirmed.source_pages,
            (2,),
        )
        self.assertEqual(
            confirmed.extraction,
            original_extraction,
        )
        self.assertFalse(
            confirmed.approved
        )

    def test_04_unresolved_source_fails_safe(self):
        document = build_feasible_document(
            [
                "Different operating evidence."
            ]
        )

        candidate = (
            analyze_feasible_evidence_pdf(
                document,
                extractor=build_extractor(
                    "Measured hardness H ranged "
                    "from 58 to 60 HRC."
                ),
            )
            .candidates[0]
        )

        self.assertEqual(
            candidate.source_location_status,
            "SOURCE_LOCATION_UNRESOLVED",
        )
        self.assertFalse(
            candidate.source_location_ready
        )

    def test_05_pdf_bytes_are_not_passed_to_f_extractor(self):
        document = build_feasible_document(
            [
                (
                    "Measured hardness H ranged "
                    "from 58 to 60 HRC."
                )
            ]
        )

        observed = {}

        def extractor(
            text,
            source_name,
        ):
            observed["text"] = text
            observed["source_name"] = (
                source_name
            )
            return []

        analyze_feasible_evidence_pdf(
            document,
            extractor=extractor,
        )

        self.assertIsInstance(
            observed["text"],
            str,
        )
        self.assertIn(
            "===== PDF PAGE 1 =====",
            observed["text"],
        )
        self.assertNotIn(
            "%PDF",
            observed["text"],
        )
        self.assertEqual(
            observed["source_name"],
            "Operating_Evidence.pdf",
        )

    def test_06_non_feasible_role_is_rejected(self):
        document = build_feasible_document(
            ["Evidence"]
        )

        document = IngestedPdfDocument(
            role="requirement",
            filename=document.filename,
            content_sha256=(
                document.content_sha256
            ),
            raw_bytes=document.raw_bytes,
            total_pages=document.total_pages,
            pages=document.pages,
            status=document.status,
            issues=document.issues,
        )

        with self.assertRaises(
            ValueError
        ):
            analyze_feasible_evidence_pdf(
                document,
                extractor=lambda *_: [],
            )


if __name__ == "__main__":
    unittest.main()
