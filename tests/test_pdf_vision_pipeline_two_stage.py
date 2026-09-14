from io import BytesIO
import unittest
from unittest.mock import patch

from pypdf import PdfWriter

from src.ai.pdf_page_triage import (
    PdfPageTriageResult,
    PdfTwoStageTriageResult,
)
from src.application import pdf_vision_pipeline as pipeline
from src.application.pdf_ingress import (
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


class PdfVisionPipelineTwoStageTest(unittest.TestCase):
    def test_01_over_budget_runs_two_stage_then_only_selected_high_detail_pages(self):
        raw = build_blank_pdf(13)

        initial = ingest_pdf_document(
            role="feasible",
            filename="large-scan.pdf",
            content=raw,
        )

        focused = PdfPageTriageResult(
            selected_page_numbers=(2, 11),
            reasons=(
                (2, "measurement table"),
                (11, "observed data"),
            ),
            summary="focused result",
        )

        decision = PdfTwoStageTriageResult(
            coarse_result=None,
            focused_result=focused,
        )

        vision_calls = []

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return f"Selected page {page_number}"

        with patch.object(
            pipeline,
            "recommend_pdf_pages_two_stage",
            return_value=decision,
            create=True,
        ) as triage:
            result = (
                pipeline.prepare_pdf_document_with_two_stage_triage(
                    initial,
                    vision_page_extractor=fake_vision,
                    triage_client=object(),
                )
            )

        triage.assert_called_once()

        kwargs = triage.call_args.kwargs

        self.assertEqual(
            kwargs["candidate_page_numbers"],
            tuple(range(1, 14)),
        )
        self.assertEqual(
            kwargs["document_role"],
            "feasible",
        )
        self.assertEqual(
            kwargs["max_selected_pages"],
            12,
        )

        self.assertEqual(
            vision_calls,
            [2, 11],
        )

        self.assertTrue(result.ready)
        self.assertEqual(
            result.selected_page_numbers,
            (2, 11),
        )
        self.assertEqual(
            result.document.status,
            "READY_FOR_SELECTED_PAGE_ANALYSIS",
        )

    def test_02_two_stage_provenance_is_preserved(self):
        raw = build_blank_pdf(30)

        initial = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=raw,
        )

        coarse = PdfPageTriageResult(
            selected_page_numbers=tuple(range(1, 25)),
            reasons=(),
            summary="coarse shortlist",
        )

        focused = PdfPageTriageResult(
            selected_page_numbers=(4, 5),
            reasons=(
                (4, "dense engineering table"),
                (5, "numeric results"),
            ),
            summary="focused shortlist",
        )

        decision = PdfTwoStageTriageResult(
            coarse_result=coarse,
            focused_result=focused,
        )

        def fake_vision(pdf_bytes, page_number):
            return f"Page {page_number}"

        with patch.object(
            pipeline,
            "recommend_pdf_pages_two_stage",
            return_value=decision,
            create=True,
        ):
            result = (
                pipeline.prepare_pdf_document_with_two_stage_triage(
                    initial,
                    vision_page_extractor=fake_vision,
                    triage_client=object(),
                )
            )

        self.assertIs(
            result.triage_result,
            focused,
        )

        self.assertIs(
            result.coarse_triage_result,
            coarse,
        )

        self.assertEqual(
            result.selected_page_numbers,
            (4, 5),
        )

    def test_03_within_budget_skips_two_stage_triage(self):
        raw = build_blank_pdf(4)

        initial = ingest_pdf_document(
            role="verification",
            filename="small-scan.pdf",
            content=raw,
        )

        vision_calls = []

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return f"Page {page_number}"

        with patch.object(
            pipeline,
            "recommend_pdf_pages_two_stage",
            create=True,
        ) as triage:
            result = (
                pipeline.prepare_pdf_document_with_two_stage_triage(
                    initial,
                    vision_page_extractor=fake_vision,
                    triage_client=object(),
                )
            )

        triage.assert_not_called()

        self.assertTrue(result.ready)
        self.assertEqual(
            vision_calls,
            [1, 2, 3, 4],
        )
        self.assertTrue(
            result.document.full_document_coverage
        )
        self.assertIsNone(
            result.coarse_triage_result
        )

    def test_04_two_stage_failure_blocks_high_detail_vision(self):
        raw = build_blank_pdf(13)

        initial = ingest_pdf_document(
            role="feasible",
            filename="large-scan.pdf",
            content=raw,
        )

        vision_calls = []

        def fake_vision(pdf_bytes, page_number):
            vision_calls.append(page_number)
            return "SHOULD NOT RUN"

        with patch.object(
            pipeline,
            "recommend_pdf_pages_two_stage",
            side_effect=RuntimeError("triage unavailable"),
            create=True,
        ):
            result = (
                pipeline.prepare_pdf_document_with_two_stage_triage(
                    initial,
                    vision_page_extractor=fake_vision,
                    triage_client=object(),
                )
            )

        self.assertFalse(result.ready)
        self.assertEqual(
            vision_calls,
            [],
        )
        self.assertIn(
            "VISION_PAGE_TRIAGE_FAILED",
            result.issue_codes,
        )


if __name__ == "__main__":
    unittest.main()
