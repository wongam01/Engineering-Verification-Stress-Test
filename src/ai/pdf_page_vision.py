from __future__ import annotations

import base64
from io import BytesIO

import pypdfium2 as pdfium


DEFAULT_VISION_MODEL = "gpt-5.6-terra"
DEFAULT_RENDER_DPI = 300


PAGE_TRANSCRIPTION_PROMPT = """
Transcribe this engineering document page faithfully.

Preserve the information that is visibly present on the page, including:
- headings and ordinary text
- table structure, row labels, and column labels
- numeric values and engineering units
- inequality symbols, ranges, tolerances, and limits
- footnotes, markers, and annotations
- large primary values and smaller adjacent or secondary values separately

Do not determine whether the page is a requirement, verification criterion,
or feasible-state evidence. Do not perform engineering verification.

Do not infer, repair, round, or invent unreadable content.
If content cannot be read reliably, mark it as uncertain or unreadable.

Return only a faithful textual transcription of the visible page content.
""".strip()


def render_pdf_page_to_png(
    pdf_bytes: bytes,
    *,
    page_number: int,
    dpi: int = DEFAULT_RENDER_DPI,
) -> bytes:
    """
    Render one 1-based PDF page to PNG bytes.

    The function performs rendering only. It does not call an AI model.
    """

    if page_number < 1:
        raise ValueError("page_number must be 1 or greater.")

    if dpi <= 0:
        raise ValueError("dpi must be greater than zero.")

    try:
        document = pdfium.PdfDocument(pdf_bytes)
    except Exception as exc:
        raise ValueError(
            f"PDF could not be opened for page rendering: {exc}"
        ) from exc

    try:
        total_pages = len(document)

        if page_number > total_pages:
            raise ValueError(
                f"page_number {page_number} exceeds "
                f"PDF page count {total_pages}."
            )

        page = document[page_number - 1]

        try:
            bitmap = page.render(
                scale=dpi / 72.0,
            )

            try:
                image = bitmap.to_pil()
                buffer = BytesIO()
                image.save(
                    buffer,
                    format="PNG",
                )
                return buffer.getvalue()
            finally:
                bitmap.close()

        finally:
            page.close()

    finally:
        document.close()


def extract_pdf_page_with_vision(
    pdf_bytes: bytes,
    *,
    page_number: int,
    client,
    model: str = DEFAULT_VISION_MODEL,
    dpi: int = DEFAULT_RENDER_DPI,
) -> str:
    """
    Render one PDF page and ask a Vision-capable model for a faithful
    transcription.

    This layer intentionally does not classify the page as Requirement,
    Verification, or Feasible Evidence. Semantic interpretation remains
    downstream.
    """

    png_bytes = render_pdf_page_to_png(
        pdf_bytes,
        page_number=page_number,
        dpi=dpi,
    )

    encoded_png = base64.b64encode(
        png_bytes
    ).decode("ascii")

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": PAGE_TRANSCRIPTION_PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            "data:image/png;base64,"
                            + encoded_png
                        ),
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    output_text = getattr(
        response,
        "output_text",
        "",
    )

    return (output_text or "").strip()
