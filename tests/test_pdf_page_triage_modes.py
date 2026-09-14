import unittest
from unittest.mock import patch

from src.ai.pdf_page_triage import (
    recommend_pdf_pages_with_vision,
)


class _FakeResponse:
    output_text = (
        '{"selected_pages":[1],'
        '"reasons":{"1":"plausible engineering evidence"},'
        '"summary":"bounded recommendation"}'
    )


class _FakeResponses:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _FakeResponse()


class _FakeClient:
    def __init__(self):
        self.responses = _FakeResponses()


class PdfPageTriageModesTest(unittest.TestCase):
    def test_01_focused_mode_uses_higher_resolution_smaller_sheets(self):
        client = _FakeClient()

        with patch(
            "src.ai.pdf_page_triage.render_pdf_contact_sheets",
            return_value=(b"png-bytes",),
        ) as render:
            recommend_pdf_pages_with_vision(
                b"pdf-bytes",
                candidate_page_numbers=(1, 2, 3, 4),
                document_role="feasible",
                max_selected_pages=2,
                client=client,
                triage_mode="focused",
            )

        render.assert_called_once_with(
            b"pdf-bytes",
            page_numbers=(1, 2, 3, 4),
            dpi=150,
            pages_per_sheet=4,
            columns=2,
        )

    def test_02_focused_mode_uses_high_detail_images(self):
        client = _FakeClient()

        with patch(
            "src.ai.pdf_page_triage.render_pdf_contact_sheets",
            return_value=(b"png-bytes",),
        ):
            recommend_pdf_pages_with_vision(
                b"pdf-bytes",
                candidate_page_numbers=(1, 2),
                document_role="requirement",
                max_selected_pages=1,
                client=client,
                triage_mode="focused",
            )

        call = client.responses.calls[0]
        content = call["input"][0]["content"]

        image_items = [
            item
            for item in content
            if item["type"] == "input_image"
        ]

        self.assertEqual(
            len(image_items),
            1,
        )
        self.assertEqual(
            image_items[0]["detail"],
            "high",
        )

    def test_03_focused_prompt_is_generic_and_dense_data_aware(self):
        client = _FakeClient()

        with patch(
            "src.ai.pdf_page_triage.render_pdf_contact_sheets",
            return_value=(b"png-bytes",),
        ):
            recommend_pdf_pages_with_vision(
                b"pdf-bytes",
                candidate_page_numbers=(1, 2),
                document_role="feasible",
                max_selected_pages=1,
                client=client,
                triage_mode="focused",
            )

        call = client.responses.calls[0]
        content = call["input"][0]["content"]

        prompt = next(
            item["text"]
            for item in content
            if item["type"] == "input_text"
        )

        prompt_lower = prompt.lower()

        self.assertIn(
            "dense numerical",
            prompt_lower,
        )
        self.assertIn(
            "small",
            prompt_lower,
        )
        self.assertIn(
            "table",
            prompt_lower,
        )

        # Case-specific hints must never appear.
        self.assertNotIn("ford", prompt_lower)
        self.assertNotIn("hrc", prompt_lower)
        self.assertNotIn("50-57", prompt_lower)
        self.assertNotIn("58-60", prompt_lower)


if __name__ == "__main__":
    unittest.main()
