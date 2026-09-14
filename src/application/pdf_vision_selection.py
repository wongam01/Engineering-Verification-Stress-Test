from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from src.application.pdf_ingress import (
    DEFAULT_MAX_VISION_PAGES,
    IngestedPdfDocument,
)


@dataclass(frozen=True)
class PdfVisionSelectionPlan:
    candidate_page_numbers: tuple[int, ...]
    max_selected_pages: int
    selection_required: bool
    automatic_page_numbers: tuple[int, ...]


@dataclass(frozen=True)
class PdfVisionSelectionValidation:
    valid: bool
    selected_page_numbers: tuple[int, ...]
    issue_codes: tuple[str, ...]


def build_pdf_vision_selection_plan(
    document: IngestedPdfDocument,
    *,
    max_selected_pages: int = DEFAULT_MAX_VISION_PAGES,
) -> PdfVisionSelectionPlan:
    """
    Build a deterministic page-selection boundary for Vision recovery.

    Only pages without usable embedded text are Vision candidates.
    Documents within the budget may process all candidates automatically.
    Documents over budget require an explicit page selection.
    """

    if max_selected_pages < 1:
        raise ValueError(
            "max_selected_pages must be at least 1."
        )

    candidate_page_numbers = tuple(
        page.page_number
        for page in document.pages
        if not page.text.strip()
    )

    selection_required = (
        len(candidate_page_numbers)
        > max_selected_pages
    )

    automatic_page_numbers = (
        ()
        if selection_required
        else candidate_page_numbers
    )

    return PdfVisionSelectionPlan(
        candidate_page_numbers=candidate_page_numbers,
        max_selected_pages=max_selected_pages,
        selection_required=selection_required,
        automatic_page_numbers=automatic_page_numbers,
    )


def validate_pdf_vision_page_selection(
    plan: PdfVisionSelectionPlan,
    selected_page_numbers: Sequence[int] | None,
) -> PdfVisionSelectionValidation:
    """
    Validate a proposed Vision page scope.

    This function does not choose pages. It only guarantees that a later
    human or AI recommendation cannot silently exceed the configured
    budget or select pages outside the actual Vision candidate set.
    """

    if selected_page_numbers is None:
        if plan.selection_required:
            return PdfVisionSelectionValidation(
                valid=False,
                selected_page_numbers=(),
                issue_codes=(
                    "VISION_PAGE_SELECTION_REQUIRED",
                ),
            )

        return PdfVisionSelectionValidation(
            valid=True,
            selected_page_numbers=(
                plan.automatic_page_numbers
            ),
            issue_codes=(),
        )

    raw_selection = tuple(selected_page_numbers)

    if any(
        isinstance(page_number, bool)
        or not isinstance(page_number, int)
        for page_number in raw_selection
    ):
        return PdfVisionSelectionValidation(
            valid=False,
            selected_page_numbers=(),
            issue_codes=(
                "VISION_PAGE_SELECTION_INVALID_TYPE",
            ),
        )

    if len(raw_selection) != len(set(raw_selection)):
        return PdfVisionSelectionValidation(
            valid=False,
            selected_page_numbers=(),
            issue_codes=(
                "VISION_PAGE_SELECTION_DUPLICATE",
            ),
        )

    if (
        len(raw_selection)
        > plan.max_selected_pages
    ):
        return PdfVisionSelectionValidation(
            valid=False,
            selected_page_numbers=(),
            issue_codes=(
                "VISION_PAGE_SELECTION_LIMIT_EXCEEDED",
            ),
        )

    if (
        plan.candidate_page_numbers
        and not raw_selection
    ):
        return PdfVisionSelectionValidation(
            valid=False,
            selected_page_numbers=(),
            issue_codes=(
                "VISION_PAGE_SELECTION_REQUIRED",
            ),
        )

    candidate_set = set(
        plan.candidate_page_numbers
    )

    if any(
        page_number not in candidate_set
        for page_number in raw_selection
    ):
        return PdfVisionSelectionValidation(
            valid=False,
            selected_page_numbers=(),
            issue_codes=(
                "VISION_PAGE_SELECTION_NOT_CANDIDATE",
            ),
        )

    return PdfVisionSelectionValidation(
        valid=True,
        selected_page_numbers=tuple(
            sorted(raw_selection)
        ),
        issue_codes=(),
    )
