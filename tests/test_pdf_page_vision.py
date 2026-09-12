from io import BytesIO
import base64
import unittest

from PIL import Image
from pypdf import PdfWriter

from src.ai.pdf_page_vision import (
    extract_pdf_page_with_vision,
    render_pdf_page_to_png,
)


def build_blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(
        width=612,
        height=792,
    )

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


class FakeResponse:
    def __init__(self, output_text):
        self.output_text = output_text


class FakeResponses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return FakeResponse(self.output_text)


class FakeClient:
    def __init__(self, output_text):
        self.responses = FakeResponses(output_text)


class PdfPageVisionTest(unittest.TestCase):
    def test_01_pdf_page_renders_to_png(self):
        raw = build_blank_pdf()

        png = render_pdf_page_to_png(
            raw,
            page_number=1,
            dpi=144,
        )

        self.assertTrue(
            png.startswith(b"\x89PNG\r\n\x1a\n")
        )

        image = Image.open(BytesIO(png))

        self.assertEqual(image.format, "PNG")
        self.assertGreater(image.width, 1000)
        self.assertGreater(image.height, 1000)


    def test_02_invalid_page_number_fails_explicitly(self):
        raw = build_blank_pdf()

        with self.assertRaises(ValueError):
            render_pdf_page_to_png(
                raw,
                page_number=0,
            )

        with self.assertRaises(ValueError):
            render_pdf_page_to_png(
                raw,
                page_number=2,
            )


    def test_03_vision_receives_png_not_raw_pdf(self):
        raw = build_blank_pdf()
        client = FakeClient(
            "  Faithful engineering page transcription.  "
        )

        result = extract_pdf_page_with_vision(
            raw,
            page_number=1,
            client=client,
            model="unit-test-model",
            dpi=144,
        )

        self.assertEqual(
            result,
            "Faithful engineering page transcription.",
        )

        self.assertEqual(
            len(client.responses.calls),
            1,
        )

        call = client.responses.calls[0]

        self.assertEqual(
            call["model"],
            "unit-test-model",
        )

        content = call["input"][0]["content"]

        text_item = next(
            item
            for item in content
            if item["type"] == "input_text"
        )
        image_item = next(
            item
            for item in content
            if item["type"] == "input_image"
        )

        self.assertEqual(
            image_item["detail"],
            "high",
        )

        prefix = "data:image/png;base64,"

        self.assertTrue(
            image_item["image_url"].startswith(prefix)
        )

        decoded = base64.b64decode(
            image_item["image_url"][len(prefix):]
        )

        self.assertTrue(
            decoded.startswith(b"\x89PNG\r\n\x1a\n")
        )
        self.assertFalse(
            decoded.startswith(b"%PDF-")
        )

        prompt = text_item["text"]

        # The Vision layer must stay case-independent.
        for forbidden in [
            "Ford",
            "Haldex",
            "NASA",
            "50-57",
            "58-60",
        ]:
            self.assertNotIn(
                forbidden,
                prompt,
            )


    def test_04_empty_model_output_remains_empty(self):
        raw = build_blank_pdf()
        client = FakeClient("   ")

        result = extract_pdf_page_with_vision(
            raw,
            page_number=1,
            client=client,
            model="unit-test-model",
            dpi=144,
        )

        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()
