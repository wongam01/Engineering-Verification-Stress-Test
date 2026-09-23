from __future__ import annotations

from src.ai.pdf_vision_cache import (
    build_pdf_vision_transcription_bundle,
    is_pdf_page_vision_cached,
    load_pdf_vision_transcription_bundle,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
    pdf_document_vision_candidate_page_numbers,
    prepare_pdf_document_with_deep_vision,
)


def restore_pdf_document_from_vision_cache(
    document: IngestedPdfDocument,
) -> IngestedPdfDocument:
    """
    Restore Vision-derived page text without making Vision API calls.

    Fast path:
        one aggregate bundle read per physical PDF.

    Fallback:
        verify existing page-level cache, build the aggregate bundle,
        then restore from the in-memory bundle.
    """

    candidate_pages = (
        pdf_document_vision_candidate_page_numbers(
            document
        )
    )

    if not candidate_pages:
        return document

    bundle = load_pdf_vision_transcription_bundle(
        document.raw_bytes,
        page_numbers=candidate_pages,
    )

    if bundle is None:
        if not all(
            is_pdf_page_vision_cached(
                document.raw_bytes,
                page_number=page_number,
            )
            for page_number in candidate_pages
        ):
            return document

        bundle = build_pdf_vision_transcription_bundle(
            document.raw_bytes,
            page_numbers=candidate_pages,
        )

    if bundle is None:
        return document

    def bundle_page_extractor(
        _pdf_bytes,
        page_number,
    ):
        transcription = bundle.get(
            page_number
        )

        if transcription is None:
            raise RuntimeError(
                "Vision transcription bundle is missing "
                f"page {page_number}."
            )

        return transcription

    return prepare_pdf_document_with_deep_vision(
        document,
        vision_page_extractor=(
            bundle_page_extractor
        ),
    )
