from io import BytesIO
from types import SimpleNamespace
import unittest

from pypdf import PdfWriter

from src.ai.pdf_page_triage import (
    DEFAULT_MAX_TRIAGE_CANDIDATE_PAGES,
    TRIAGE_PROMPT,
    recommend_pdf_pages_with_vision,
    render_pdf_contact_sheets,
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


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            output_text=self.output_text
        )


class FakeClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(
            output_text
        )


class PdfPageTriageTest(unittest.TestCase):
    def test_01_contact_sheets_cover_all_candidate_pages(self):
        raw = build_blank_pdf(13)

        sheets = render_pdf_contact_sheets(
            raw,
            page_numbers=list(range(1, 14)),
        )

        self.assertEqual(
            len(sheets),
            2,
        )

        for sheet in sheets:
            self.assertTrue(
                sheet.startswith(
                    b"\x89PNG\r\n\x1a\n"
                )
            )

    def test_02_triage_sends_png_overviews_not_raw_pdf(self):
        raw = build_blank_pdf(13)

        client = FakeClient(
            """
            {
              "selected_pages": [2, 11],
              "reasons": {
                "2": "table-like engineering content",
                "11": "measurement-oriented page"
              },
              "summary": "Two plausible evidence pages."
            }
            """
        )

        result = recommend_pdf_pages_with_vision(
            raw,
            candidate_page_numbers=(
                tuple(range(1, 14))
            ),
            document_role="feasible",
            max_selected_pages=12,
            client=client,
        )

        self.assertEqual(
            result.selected_page_numbers,
            (2, 11),
        )

        self.assertEqual(
            len(client.responses.calls),
            1,
        )

        call = client.responses.calls[0]
        content = call["input"][0]["content"]

        images = [
            item
            for item in content
            if item["type"] == "input_image"
        ]

        self.assertEqual(
            len(images),
            2,
        )

        for image in images:
            self.assertTrue(
                image["image_url"].startswith(
                    "data:image/png;base64,"
                )
            )
            self.assertEqual(
                image["detail"],
                "low",
            )

    def test_03_model_cannot_select_non_candidate_page(self):
        raw = build_blank_pdf(13)

        client = FakeClient(
            """
            {
              "selected_pages": [99],
              "reasons": {
                "99": "invalid"
              },
              "summary": "invalid"
            }
            """
        )

        with self.assertRaises(ValueError):
            recommend_pdf_pages_with_vision(
                raw,
                candidate_page_numbers=(
                    tuple(range(1, 14))
                ),
                document_role="requirement",
                max_selected_pages=12,
                client=client,
            )

    def test_04_model_cannot_exceed_selection_budget(self):
        raw = build_blank_pdf(13)

        selected = list(range(1, 14))

        client = FakeClient(
            (
                '{"selected_pages": '
                + str(selected).replace("'", '"')
                + ', "reasons": {}, '
                + '"summary": "too many"}'
            )
        )

        with self.assertRaises(ValueError):
            recommend_pdf_pages_with_vision(
                raw,
                candidate_page_numbers=(
                    tuple(range(1, 14))
                ),
                document_role="verification",
                max_selected_pages=12,
                client=client,
            )

    def test_05_invalid_json_fails_safe(self):
        raw = build_blank_pdf(13)

        client = FakeClient(
            "not-json"
        )

        with self.assertRaises(ValueError):
            recommend_pdf_pages_with_vision(
                raw,
                candidate_page_numbers=(
                    tuple(range(1, 14))
                ),
                document_role="feasible",
                max_selected_pages=12,
                client=client,
            )

    def test_06_triage_prompt_is_case_independent(self):
        lowered = TRIAGE_PROMPT.lower()

        for forbidden in (
            "ford",
            "nasa",
            "haldex",
            "hrc",
            "50-57",
            "50–57",
        ):
            self.assertNotIn(
                forbidden,
                lowered,
            )

    def test_07_candidate_limit_is_explicit(self):
        raw = build_blank_pdf(
            DEFAULT_MAX_TRIAGE_CANDIDATE_PAGES
            + 1
        )

        client = FakeClient(
            """
            {
              "selected_pages": [],
              "reasons": {},
              "summary": "unused"
            }
            """
        )

        with self.assertRaises(ValueError):
            recommend_pdf_pages_with_vision(
                raw,
                candidate_page_numbers=tuple(
                    range(
                        1,
                        DEFAULT_MAX_TRIAGE_CANDIDATE_PAGES
                        + 2,
                    )
                ),
                document_role="requirement",
                max_selected_pages=12,
                client=client,
            )

        self.assertEqual(
            client.responses.calls,
            [],
        )


if __name__ == "__main__":
    unittest.main()
