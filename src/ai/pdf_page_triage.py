from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from io import BytesIO
from typing import Sequence

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

from src.ai.pdf_page_vision import DEFAULT_VISION_MODEL


DEFAULT_TRIAGE_MODEL = DEFAULT_VISION_MODEL
DEFAULT_TRIAGE_RENDER_DPI = 72
DEFAULT_TRIAGE_PAGES_PER_SHEET = 8
DEFAULT_TRIAGE_COLUMNS = 2
DEFAULT_MAX_TRIAGE_CANDIDATE_PAGES = 96

FOCUSED_TRIAGE_RENDER_DPI = 150
FOCUSED_TRIAGE_PAGES_PER_SHEET = 4
FOCUSED_TRIAGE_COLUMNS = 2

FOCUSED_TRIAGE_GUIDANCE = """
Focused review instructions:

- Give dense numerical tables, small engineering text, measurement
  result tables, specification ranges, footnotes, and compact
  annotations the same attention as large photographs or diagrams.
- Do not prefer visually large images merely because they are easier
  to see.
- If small text is still unreadable, do not infer its contents.
- Continue to select pages only by their visible engineering relevance.
"""

DEFAULT_THUMBNAIL_WIDTH = 500
DEFAULT_THUMBNAIL_HEIGHT = 650
DEFAULT_LABEL_HEIGHT = 32
DEFAULT_CELL_MARGIN = 12


TRIAGE_PROMPT = """
You are triaging pages of an engineering document for downstream
source-evidence transcription.

The supplied images are LOW-RESOLUTION CONTACT SHEETS. Each page
thumbnail is labeled with its original PDF page number.

Your task is only to recommend which pages should receive later
high-detail Vision transcription.

Use the document role when judging relevance:

- requirement:
  pages likely to contain engineering requirements, specifications,
  allowable ranges, limits, tolerances, drawing notes, or design
  criteria.

- verification:
  pages likely to contain inspection rules, test procedures,
  acceptance criteria, pass/fail limits, verification methods,
  measurement requirements, or quality-control criteria.

- feasible:
  pages likely to contain observed, measured, test, production,
  field, laboratory, or operational data that could support an
  actually observed feasible state or range.

Important rules:
- Do NOT perform engineering verification.
- Do NOT decide whether a requirement is violated.
- Do NOT infer unreadable values.
- Do NOT repair or invent document content.
- Do NOT use an expected answer.
- Select only from the explicitly supplied candidate page numbers.
- Recommend no more than the supplied maximum.
- If uncertain, prefer a diverse set of plausible pages and state
  the uncertainty in the summary.

Return JSON only in this exact shape:

{
  "selected_pages": [1, 2],
  "reasons": {
    "1": "brief visual reason",
    "2": "brief visual reason"
  },
  "summary": "brief triage summary"
}
""".strip()


@dataclass(frozen=True)
class PdfPageTriageResult:
    selected_page_numbers: tuple[int, ...]
    reasons: tuple[tuple[int, str], ...]
    summary: str


def _canonical_page_numbers(
    page_numbers: Sequence[int],
) -> tuple[int, ...]:
    values = tuple(page_numbers)

    if not values:
        raise ValueError(
            "At least one candidate page is required."
        )

    if any(
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        for page_number in values
    ):
        raise ValueError(
            "Candidate page numbers must be integers."
        )

    if any(page_number < 1 for page_number in values):
        raise ValueError(
            "Candidate page numbers must be 1-based."
        )

    if len(values) != len(set(values)):
        raise ValueError(
            "Candidate page numbers must be unique."
        )

    return tuple(sorted(values))


def render_pdf_contact_sheets(
    pdf_bytes: bytes,
    *,
    page_numbers: Sequence[int],
    dpi: int = DEFAULT_TRIAGE_RENDER_DPI,
    pages_per_sheet: int = DEFAULT_TRIAGE_PAGES_PER_SHEET,
    columns: int = DEFAULT_TRIAGE_COLUMNS,
) -> tuple[bytes, ...]:
    """
    Render low-resolution page overview sheets for triage.

    This is not source transcription. Page labels preserve the original
    1-based PDF page identity for later selection.
    """

    candidate_pages = _canonical_page_numbers(
        page_numbers
    )

    if dpi < 36:
        raise ValueError(
            "Triage render DPI must be at least 36."
        )

    if pages_per_sheet < 1:
        raise ValueError(
            "pages_per_sheet must be at least 1."
        )

    if columns < 1:
        raise ValueError(
            "columns must be at least 1."
        )

    rows = (
        pages_per_sheet + columns - 1
    ) // columns

    cell_width = (
        DEFAULT_THUMBNAIL_WIDTH
        + 2 * DEFAULT_CELL_MARGIN
    )
    cell_height = (
        DEFAULT_THUMBNAIL_HEIGHT
        + DEFAULT_LABEL_HEIGHT
        + 2 * DEFAULT_CELL_MARGIN
    )

    document = pdfium.PdfDocument(pdf_bytes)

    try:
        total_pages = len(document)

        if any(
            page_number > total_pages
            for page_number in candidate_pages
        ):
            raise ValueError(
                "Candidate page number exceeds PDF page count."
            )

        sheets: list[bytes] = []

        for offset in range(
            0,
            len(candidate_pages),
            pages_per_sheet,
        ):
            sheet_pages = candidate_pages[
                offset:offset + pages_per_sheet
            ]

            canvas = Image.new(
                "RGB",
                (
                    cell_width * columns,
                    cell_height * rows,
                ),
                "white",
            )

            draw = ImageDraw.Draw(canvas)

            for index, page_number in enumerate(
                sheet_pages
            ):
                row = index // columns
                column = index % columns

                page = document[
                    page_number - 1
                ]
                bitmap = None

                try:
                    bitmap = page.render(
                        scale=dpi / 72.0
                    )

                    image = bitmap.to_pil().convert(
                        "RGB"
                    )

                    image.thumbnail(
                        (
                            DEFAULT_THUMBNAIL_WIDTH,
                            DEFAULT_THUMBNAIL_HEIGHT,
                        ),
                        Image.Resampling.LANCZOS,
                    )

                    x = (
                        column * cell_width
                        + DEFAULT_CELL_MARGIN
                    )
                    y = (
                        row * cell_height
                        + DEFAULT_CELL_MARGIN
                        + DEFAULT_LABEL_HEIGHT
                    )

                    canvas.paste(
                        image,
                        (x, y),
                    )

                    draw.text(
                        (
                            column * cell_width
                            + DEFAULT_CELL_MARGIN,
                            row * cell_height
                            + DEFAULT_CELL_MARGIN,
                        ),
                        f"PDF page {page_number}",
                        fill="black",
                    )
                finally:
                    if bitmap is not None:
                        bitmap.close()

                    page.close()

            buffer = BytesIO()
            canvas.save(
                buffer,
                format="PNG",
            )
            sheets.append(
                buffer.getvalue()
            )

        return tuple(sheets)

    finally:
        document.close()


def _parse_triage_output(
    output_text: str,
    *,
    candidate_page_numbers: tuple[int, ...],
    max_selected_pages: int,
) -> PdfPageTriageResult:
    raw = output_text.strip()

    if raw.startswith("```"):
        lines = raw.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        raw = "\n".join(lines).strip()

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Vision triage did not return valid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            "Vision triage output must be a JSON object."
        )

    selected = payload.get(
        "selected_pages"
    )

    if not isinstance(selected, list):
        raise ValueError(
            "selected_pages must be a JSON array."
        )

    if any(
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        for page_number in selected
    ):
        raise ValueError(
            "selected_pages must contain integers."
        )

    if len(selected) != len(set(selected)):
        raise ValueError(
            "selected_pages must not contain duplicates."
        )

    if len(selected) > max_selected_pages:
        raise ValueError(
            "Vision triage exceeded the page-selection budget."
        )

    candidate_set = set(
        candidate_page_numbers
    )

    if any(
        page_number not in candidate_set
        for page_number in selected
    ):
        raise ValueError(
            "Vision triage selected a non-candidate page."
        )

    reasons_payload = payload.get(
        "reasons",
        {},
    )

    if not isinstance(reasons_payload, dict):
        raise ValueError(
            "reasons must be a JSON object."
        )

    reasons: list[tuple[int, str]] = []

    for page_number in selected:
        reason = reasons_payload.get(
            str(page_number),
            "",
        )

        if not isinstance(reason, str):
            raise ValueError(
                "Each triage reason must be text."
            )

        reasons.append(
            (
                page_number,
                reason.strip(),
            )
        )

    summary = payload.get(
        "summary",
        "",
    )

    if not isinstance(summary, str):
        raise ValueError(
            "summary must be text."
        )

    return PdfPageTriageResult(
        selected_page_numbers=tuple(
            sorted(selected)
        ),
        reasons=tuple(
            sorted(
                reasons,
                key=lambda item: item[0],
            )
        ),
        summary=summary.strip(),
    )


def recommend_pdf_pages_with_vision(
    pdf_bytes: bytes,
    *,
    candidate_page_numbers: Sequence[int],
    document_role: str,
    max_selected_pages: int,
    client,
    model: str = DEFAULT_TRIAGE_MODEL,
    triage_mode: str = "coarse",
) -> PdfPageTriageResult:
    """
    Recommend a bounded set of pages for later high-detail transcription.

    The raw PDF is never sent to the AI service. Only low-resolution
    PNG contact sheets are supplied.
    """

    if triage_mode not in {
        "coarse",
        "focused",
    }:
        raise ValueError(
            "triage_mode must be coarse or focused."
        )

    if document_role not in {
        "requirement",
        "verification",
        "feasible",
    }:
        raise ValueError(
            "document_role must be requirement, verification, or feasible."
        )

    if max_selected_pages < 1:
        raise ValueError(
            "max_selected_pages must be at least 1."
        )

    candidate_pages = _canonical_page_numbers(
        candidate_page_numbers
    )

    if (
        len(candidate_pages)
        > DEFAULT_MAX_TRIAGE_CANDIDATE_PAGES
    ):
        raise ValueError(
            "Vision triage candidate-page limit exceeded."
        )

    if triage_mode == "focused":
        contact_sheets = render_pdf_contact_sheets(
            pdf_bytes,
            page_numbers=candidate_pages,
            dpi=FOCUSED_TRIAGE_RENDER_DPI,
            pages_per_sheet=(
                FOCUSED_TRIAGE_PAGES_PER_SHEET
            ),
            columns=FOCUSED_TRIAGE_COLUMNS,
        )
    else:
        contact_sheets = render_pdf_contact_sheets(
            pdf_bytes,
            page_numbers=candidate_pages,
        )

    prompt = (
        TRIAGE_PROMPT
        + (
            "\n\n"
            + FOCUSED_TRIAGE_GUIDANCE
            if triage_mode == "focused"
            else ""
        )
        + "\n\nDocument role: "
        + document_role
        + "\nCandidate PDF pages: "
        + ", ".join(
            str(page_number)
            for page_number in candidate_pages
        )
        + "\nMaximum pages to recommend: "
        + str(max_selected_pages)
    )

    content = [
        {
            "type": "input_text",
            "text": prompt,
        }
    ]

    for sheet in contact_sheets:
        encoded = base64.b64encode(
            sheet
        ).decode("ascii")

        content.append(
            {
                "type": "input_image",
                "image_url": (
                    "data:image/png;base64,"
                    + encoded
                ),
                "detail": (
                    "high"
                    if triage_mode == "focused"
                    else "low"
                ),
            }
        )

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": content,
            }
        ],
    )

    return _parse_triage_output(
        response.output_text,
        candidate_page_numbers=(
            candidate_pages
        ),
        max_selected_pages=(
            max_selected_pages
        ),
    )


DEFAULT_FOCUSED_TRIAGE_CANDIDATE_PAGES = 24


@dataclass(frozen=True)
class PdfTwoStageTriageResult:
    coarse_result: PdfPageTriageResult | None
    focused_result: PdfPageTriageResult

    @property
    def selected_page_numbers(self) -> tuple[int, ...]:
        return self.focused_result.selected_page_numbers

    @property
    def reasons(self) -> tuple[tuple[int, str], ...]:
        return self.focused_result.reasons

    @property
    def summary(self) -> str:
        return self.focused_result.summary


def recommend_pdf_pages_two_stage(
    pdf_bytes: bytes,
    *,
    candidate_page_numbers: Sequence[int],
    document_role: str,
    max_selected_pages: int,
    client,
    model: str = DEFAULT_TRIAGE_MODEL,
) -> PdfTwoStageTriageResult:
    """
    Perform bounded two-stage engineering-document page triage.

    Smaller candidate sets go directly to focused review so that
    potentially relevant pages are not discarded by a coarse pass.

    Larger candidate sets are first reduced with low-resolution
    coarse triage, then reranked with focused higher-resolution
    review.

    This function only selects pages for later transcription.
    It does not perform engineering verification.
    """

    if max_selected_pages < 1:
        raise ValueError(
            "max_selected_pages must be at least 1."
        )

    candidate_pages = _canonical_page_numbers(
        candidate_page_numbers
    )

    if not candidate_pages:
        raise ValueError(
            "candidate_page_numbers must not be empty."
        )

    focused_candidate_limit = max(
        DEFAULT_FOCUSED_TRIAGE_CANDIDATE_PAGES,
        max_selected_pages,
    )

    coarse_result: PdfPageTriageResult | None = None

    if len(candidate_pages) > focused_candidate_limit:
        coarse_result = recommend_pdf_pages_with_vision(
            pdf_bytes,
            candidate_page_numbers=candidate_pages,
            document_role=document_role,
            max_selected_pages=focused_candidate_limit,
            client=client,
            model=model,
            triage_mode="coarse",
        )

        if not coarse_result.selected_page_numbers:
            raise ValueError(
                "Coarse Vision triage returned no candidate pages."
            )

        focused_candidate_pages = (
            coarse_result.selected_page_numbers
        )
    else:
        focused_candidate_pages = candidate_pages

    focused_result = recommend_pdf_pages_with_vision(
        pdf_bytes,
        candidate_page_numbers=focused_candidate_pages,
        document_role=document_role,
        max_selected_pages=max_selected_pages,
        client=client,
        model=model,
        triage_mode="focused",
    )

    return PdfTwoStageTriageResult(
        coarse_result=coarse_result,
        focused_result=focused_result,
    )
