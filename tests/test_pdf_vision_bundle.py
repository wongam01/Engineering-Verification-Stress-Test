import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.ai.pdf_vision_cache import (
    build_pdf_vision_transcription_bundle,
    extract_pdf_page_with_vision_cached,
    load_pdf_vision_transcription_bundle,
)


class PdfVisionBundleTest(unittest.TestCase):
    def test_bundle_requires_complete_page_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            result = (
                build_pdf_vision_transcription_bundle(
                    b"%PDF-bundle-incomplete",
                    page_numbers=(1, 2),
                    cache_dir=Path(temp),
                )
            )

        self.assertIsNone(result)

    def test_bundle_builds_from_page_cache(self):
        pdf_bytes = b"%PDF-bundle"

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            with patch(
                "src.ai.pdf_vision_cache."
                "extract_pdf_page_with_vision",
                side_effect=lambda *args, **kwargs: (
                    f"page-{kwargs['page_number']}"
                ),
            ):
                for page_number in (1, 2, 3):
                    extract_pdf_page_with_vision_cached(
                        pdf_bytes,
                        page_number=page_number,
                        client=object(),
                        cache_dir=cache_dir,
                    )

            built = (
                build_pdf_vision_transcription_bundle(
                    pdf_bytes,
                    page_numbers=(1, 2, 3),
                    cache_dir=cache_dir,
                )
            )

            self.assertEqual(
                built,
                {
                    1: "page-1",
                    2: "page-2",
                    3: "page-3",
                },
            )

            loaded = (
                load_pdf_vision_transcription_bundle(
                    pdf_bytes,
                    page_numbers=(1, 2, 3),
                    cache_dir=cache_dir,
                )
            )

            self.assertEqual(
                loaded,
                built,
            )

    def test_bundle_load_does_not_need_page_files_again(self):
        pdf_bytes = b"%PDF-bundle-fast"

        with tempfile.TemporaryDirectory() as temp:
            cache_dir = Path(temp)

            with patch(
                "src.ai.pdf_vision_cache."
                "extract_pdf_page_with_vision",
                return_value="cached text",
            ):
                for page_number in (1, 2):
                    extract_pdf_page_with_vision_cached(
                        pdf_bytes,
                        page_number=page_number,
                        client=object(),
                        cache_dir=cache_dir,
                    )

            built = (
                build_pdf_vision_transcription_bundle(
                    pdf_bytes,
                    page_numbers=(1, 2),
                    cache_dir=cache_dir,
                )
            )

            self.assertIsNotNone(built)

            with patch(
                "src.ai.pdf_vision_cache."
                "load_cached_pdf_page_transcription",
                side_effect=AssertionError(
                    "page cache should not be reread"
                ),
            ):
                loaded = (
                    load_pdf_vision_transcription_bundle(
                        pdf_bytes,
                        page_numbers=(1, 2),
                        cache_dir=cache_dir,
                    )
                )

            self.assertEqual(
                loaded,
                {
                    1: "cached text",
                    2: "cached text",
                },
            )


if __name__ == "__main__":
    unittest.main()
