from io import BytesIO
import unittest

from pypdf import PdfWriter

from src.application.pdf_ingress import (
    ingest_pdf_document,
)
from src.application.pdf_vision_selection import (
    build_pdf_vision_selection_plan,
    validate_pdf_vision_page_selection,
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


class PdfVisionSelectionTest(unittest.TestCase):
    def test_01_over_budget_requires_selection(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="thirteen-pages.pdf",
            content=build_blank_pdf(13),
        )

        plan = build_pdf_vision_selection_plan(
            document
        )

        self.assertEqual(
            plan.candidate_page_numbers,
            tuple(range(1, 14)),
        )
        self.assertEqual(
            plan.max_selected_pages,
            12,
        )
        self.assertTrue(
            plan.selection_required
        )
        self.assertEqual(
            plan.automatic_page_numbers,
            (),
        )

    def test_02_within_budget_selects_all_automatically(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="twelve-pages.pdf",
            content=build_blank_pdf(12),
        )

        plan = build_pdf_vision_selection_plan(
            document
        )

        self.assertFalse(
            plan.selection_required
        )
        self.assertEqual(
            plan.automatic_page_numbers,
            tuple(range(1, 13)),
        )

        validation = (
            validate_pdf_vision_page_selection(
                plan,
                None,
            )
        )

        self.assertTrue(validation.valid)
        self.assertEqual(
            validation.selected_page_numbers,
            tuple(range(1, 13)),
        )

    def test_03_valid_explicit_selection_is_canonicalized(self):
        document = ingest_pdf_document(
            role="verification",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        plan = build_pdf_vision_selection_plan(
            document
        )

        validation = (
            validate_pdf_vision_page_selection(
                plan,
                [13, 1, 4],
            )
        )

        self.assertTrue(validation.valid)
        self.assertEqual(
            validation.selected_page_numbers,
            (1, 4, 13),
        )
        self.assertEqual(
            validation.issue_codes,
            (),
        )

    def test_04_selection_cannot_exceed_budget(self):
        document = ingest_pdf_document(
            role="feasible",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        plan = build_pdf_vision_selection_plan(
            document
        )

        validation = (
            validate_pdf_vision_page_selection(
                plan,
                list(range(1, 14)),
            )
        )

        self.assertFalse(validation.valid)
        self.assertIn(
            "VISION_PAGE_SELECTION_LIMIT_EXCEEDED",
            validation.issue_codes,
        )

    def test_05_non_candidate_page_is_rejected(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        plan = build_pdf_vision_selection_plan(
            document
        )

        validation = (
            validate_pdf_vision_page_selection(
                plan,
                [1, 4, 99],
            )
        )

        self.assertFalse(validation.valid)
        self.assertIn(
            "VISION_PAGE_SELECTION_NOT_CANDIDATE",
            validation.issue_codes,
        )

    def test_06_duplicate_page_is_rejected(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        plan = build_pdf_vision_selection_plan(
            document
        )

        validation = (
            validate_pdf_vision_page_selection(
                plan,
                [1, 1, 4],
            )
        )

        self.assertFalse(validation.valid)
        self.assertIn(
            "VISION_PAGE_SELECTION_DUPLICATE",
            validation.issue_codes,
        )

    def test_07_over_budget_without_selection_is_explicit(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="large-scan.pdf",
            content=build_blank_pdf(13),
        )

        plan = build_pdf_vision_selection_plan(
            document
        )

        validation = (
            validate_pdf_vision_page_selection(
                plan,
                None,
            )
        )

        self.assertFalse(validation.valid)
        self.assertEqual(
            validation.selected_page_numbers,
            (),
        )
        self.assertIn(
            "VISION_PAGE_SELECTION_REQUIRED",
            validation.issue_codes,
        )


if __name__ == "__main__":
    unittest.main()
