import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ai.pdf_vision_cache import (
    build_pdf_page_vision_cache_key,
    extract_pdf_page_with_vision_cached,
    is_pdf_page_vision_cached,
    load_cached_pdf_page_transcription,
    warm_pdf_page_vision_cache,
)


class PdfVisionCacheTest(unittest.TestCase):
    def test_cache_miss_then_hit_calls_vision_once(self):
        pdf_bytes = b"%PDF-cache-test"

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            with patch(
                "src.ai.pdf_vision_cache."
                "extract_pdf_page_with_vision",
                return_value="page transcription",
            ) as raw_vision:
                first = (
                    extract_pdf_page_with_vision_cached(
                        pdf_bytes,
                        page_number=2,
                        client=object(),
                        cache_dir=cache_dir,
                    )
                )

                second = (
                    extract_pdf_page_with_vision_cached(
                        pdf_bytes,
                        page_number=2,
                        client=object(),
                        cache_dir=cache_dir,
                    )
                )

            self.assertEqual(
                first,
                "page transcription",
            )
            self.assertEqual(
                second,
                "page transcription",
            )
            self.assertEqual(
                raw_vision.call_count,
                1,
            )

    def test_cache_key_changes_by_page(self):
        pdf_bytes = b"%PDF-key-test"

        page_1 = build_pdf_page_vision_cache_key(
            pdf_bytes,
            page_number=1,
        )

        page_2 = build_pdf_page_vision_cache_key(
            pdf_bytes,
            page_number=2,
        )

        self.assertNotEqual(
            page_1,
            page_2,
        )

    def test_cache_is_pdf_specific(self):
        first = build_pdf_page_vision_cache_key(
            b"%PDF-A",
            page_number=1,
        )

        second = build_pdf_page_vision_cache_key(
            b"%PDF-B",
            page_number=1,
        )

        self.assertNotEqual(
            first,
            second,
        )

    def test_load_returns_none_when_cache_absent(self):
        with tempfile.TemporaryDirectory() as temp:
            result = load_cached_pdf_page_transcription(
                b"%PDF-none",
                page_number=1,
                cache_dir=Path(temp),
            )

        self.assertIsNone(result)

    def test_is_cached_after_successful_write(self):
        pdf_bytes = b"%PDF-status"

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            with patch(
                "src.ai.pdf_vision_cache."
                "extract_pdf_page_with_vision",
                return_value="text",
            ):
                extract_pdf_page_with_vision_cached(
                    pdf_bytes,
                    page_number=1,
                    client=object(),
                    cache_dir=cache_dir,
                )

            self.assertTrue(
                is_pdf_page_vision_cached(
                    pdf_bytes,
                    page_number=1,
                    cache_dir=cache_dir,
                )
            )

    def test_exception_is_not_cached(self):
        pdf_bytes = b"%PDF-error"

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            with patch(
                "src.ai.pdf_vision_cache."
                "extract_pdf_page_with_vision",
                side_effect=RuntimeError("boom"),
            ):
                with self.assertRaises(RuntimeError):
                    extract_pdf_page_with_vision_cached(
                        pdf_bytes,
                        page_number=1,
                        client=object(),
                        cache_dir=cache_dir,
                    )

            self.assertFalse(
                is_pdf_page_vision_cached(
                    pdf_bytes,
                    page_number=1,
                    cache_dir=cache_dir,
                )
            )

    def test_warm_cache_reuses_existing_pages(self):
        pdf_bytes = b"%PDF-warm"

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            class Response:
                output_text = "transcribed"

            class Responses:
                def __init__(self):
                    self.call_count = 0

                def create(self, **kwargs):
                    self.call_count += 1
                    return Response()

            class Client:
                def __init__(self):
                    self.responses = Responses()

            client = Client()

            with patch(
                "src.ai.pdf_vision_cache."
                "render_pdf_page_to_png",
                side_effect=lambda *args, **kwargs: (
                    f"png-{kwargs['page_number']}".encode()
                ),
            ) as render:
                warm_pdf_page_vision_cache(
                    pdf_bytes,
                    page_numbers=(1, 2, 3, 4),
                    client=client,
                    cache_dir=cache_dir,
                    max_workers=2,
                )

                self.assertEqual(
                    render.call_count,
                    4,
                )
                self.assertEqual(
                    client.responses.call_count,
                    4,
                )

                warm_pdf_page_vision_cache(
                    pdf_bytes,
                    page_numbers=(1, 2, 3, 4),
                    client=client,
                    cache_dir=cache_dir,
                    max_workers=2,
                )

                self.assertEqual(
                    render.call_count,
                    4,
                )
                self.assertEqual(
                    client.responses.call_count,
                    4,
                )

    def test_parallel_workers_never_render_inside_workers(self):
        pdf_bytes = b"%PDF-render-safety"

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            rendered = []

            def fake_render(*args, **kwargs):
                rendered.append(
                    kwargs["page_number"]
                )
                return b"png"

            with patch(
                "src.ai.pdf_vision_cache."
                "render_pdf_page_to_png",
                side_effect=fake_render,
            ), patch(
                "src.ai.pdf_vision_cache."
                "_transcribe_rendered_png_with_vision",
                return_value="text",
            ) as transcribe:
                warm_pdf_page_vision_cache(
                    pdf_bytes,
                    page_numbers=(1, 2, 3, 4),
                    client=object(),
                    cache_dir=cache_dir,
                    max_workers=4,
                )

            self.assertEqual(
                rendered,
                [1, 2, 3, 4],
            )
            self.assertEqual(
                transcribe.call_count,
                4,
            )


if __name__ == "__main__":
    unittest.main()
