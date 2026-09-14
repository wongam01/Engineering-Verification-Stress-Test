from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Callable, Literal, Sequence

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from src.application.semantic_ingress import (
    SemanticDocument,
    SemanticRole,
    SemanticSourcePage,
)


PdfDocumentRole = Literal[
    "requirement",
    "verification",
    "feasible",
]


PdfIssueSeverity = Literal[
    "ERROR",
    "WARNING",
]


VisionPageExtractor = Callable[[bytes, int], str]


@dataclass(frozen=True)
class PdfIngestionIssue:
    code: str
    message: str
    severity: PdfIssueSeverity


@dataclass(frozen=True)
class PdfPageText:
    page_number: int
    text: str
    text_sha256: str


@dataclass(frozen=True)
class IngestedPdfDocument:
    role: PdfDocumentRole
    filename: str
    content_sha256: str
    raw_bytes: bytes
    total_pages: int
    pages: tuple[PdfPageText, ...]
    status: str
    issues: tuple[PdfIngestionIssue, ...] = ()
    vision_processed_page_numbers: tuple[int, ...] = ()
    vision_unprocessed_candidate_page_numbers: tuple[int, ...] = ()

    @property
    def ready_for_semantic_analysis(self) -> bool:
        return self.status in {
            "READY_FOR_SEMANTIC_ANALYSIS",
            "READY_FOR_SELECTED_PAGE_ANALYSIS",
        }

    @property
    def full_document_coverage(self) -> bool:
        return (
            self.ready_for_semantic_analysis
            and not self.vision_unprocessed_candidate_page_numbers
        )

    def page(self, page_number: int) -> PdfPageText | None:
        for page in self.pages:
            if page.page_number == page_number:
                return page

        return None


@dataclass(frozen=True)
class PdfDocumentSetValidation:
    status: str
    issues: tuple[PdfIngestionIssue, ...]

    @property
    def valid(self) -> bool:
        return not any(
            issue.severity == "ERROR"
            for issue in self.issues
        )


DEFAULT_MAX_PDF_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PDF_PAGES = 200
DEFAULT_MAX_VISION_PAGES = 12
DEFAULT_MAX_EXTRACTED_CHARACTERS = 500_000


def _issue(
    code: str,
    message: str,
    severity: PdfIssueSeverity = "ERROR",
) -> PdfIngestionIssue:
    return PdfIngestionIssue(
        code=code,
        message=message,
        severity=severity,
    )


def _failed_document(
    *,
    role: PdfDocumentRole,
    filename: str,
    raw_bytes: bytes,
    content_sha256: str,
    status: str,
    issues: Sequence[PdfIngestionIssue],
    total_pages: int = 0,
    pages: Sequence[PdfPageText] = (),
    vision_processed_page_numbers: Sequence[int] = (),
    vision_unprocessed_candidate_page_numbers: Sequence[int] = (),
) -> IngestedPdfDocument:
    return IngestedPdfDocument(
        role=role,
        filename=filename,
        content_sha256=content_sha256,
        raw_bytes=raw_bytes,
        total_pages=total_pages,
        pages=tuple(pages),
        status=status,
        issues=tuple(issues),
        vision_processed_page_numbers=tuple(
            vision_processed_page_numbers
        ),
        vision_unprocessed_candidate_page_numbers=tuple(
            vision_unprocessed_candidate_page_numbers
        ),
    )


def ingest_pdf_document(
    *,
    role: PdfDocumentRole,
    filename: str,
    content: bytes,
    max_bytes: int = DEFAULT_MAX_PDF_BYTES,
    max_pages: int = DEFAULT_MAX_PDF_PAGES,
    max_extracted_characters: int = (
        DEFAULT_MAX_EXTRACTED_CHARACTERS
    ),
    max_vision_pages: int = DEFAULT_MAX_VISION_PAGES,
    vision_page_numbers: Sequence[int] | None = None,
    vision_page_extractor: VisionPageExtractor | None = None,
) -> IngestedPdfDocument:
    """
    Read a PDF and preserve page-level source provenance.

    Embedded text is extracted first without AI. When a Vision page
    extractor is supplied, only pages without usable embedded text are
    eligible for Vision fallback, and the full candidate count is
    checked against the configured Vision budget before any Vision call.

    Invalid, encrypted, and over-limit documents are returned as
    explicit fail-safe results. Text is never silently truncated.
    """

    if role not in {
        "requirement",
        "verification",
        "feasible",
    }:
        raise ValueError(
            "PDF role must be requirement, verification, or feasible."
        )

    raw_bytes = bytes(content)
    safe_filename = Path(filename).name.strip()
    content_hash = sha256(raw_bytes).hexdigest()

    if not safe_filename:
        return _failed_document(
            role=role,
            filename="unnamed.pdf",
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="INVALID_PDF",
            issues=[
                _issue(
                    "PDF_FILENAME_MISSING",
                    "The uploaded PDF filename is missing.",
                )
            ],
        )

    if not raw_bytes:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="EMPTY_PDF",
            issues=[
                _issue(
                    "PDF_BYTES_EMPTY",
                    "The uploaded PDF is empty.",
                )
            ],
        )

    if len(raw_bytes) > max_bytes:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="DOCUMENT_LIMIT_EXCEEDED",
            issues=[
                _issue(
                    "PDF_BYTE_LIMIT_EXCEEDED",
                    "The uploaded PDF exceeds the configured size limit.",
                )
            ],
        )

    if b"%PDF-" not in raw_bytes[:1024]:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="INVALID_PDF",
            issues=[
                _issue(
                    "PDF_HEADER_INVALID",
                    "The uploaded file does not contain a valid PDF header.",
                )
            ],
        )

    try:
        reader = PdfReader(
            BytesIO(raw_bytes),
            strict=False,
        )
    except (PdfReadError, ValueError, OSError) as exc:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="INVALID_PDF",
            issues=[
                _issue(
                    "PDF_READ_FAILED",
                    "The uploaded PDF could not be parsed: "
                    + str(exc),
                )
            ],
        )

    if reader.is_encrypted:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="ENCRYPTED_PDF_UNSUPPORTED",
            issues=[
                _issue(
                    "PDF_ENCRYPTED",
                    "Encrypted PDFs are not supported in Phase 5A.",
                )
            ],
        )

    try:
        total_pages = len(reader.pages)
    except (PdfReadError, ValueError, KeyError) as exc:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="PDF_EXTRACTION_FAILED",
            issues=[
                _issue(
                    "PDF_PAGE_INDEX_FAILED",
                    "PDF page metadata could not be read: "
                    + str(exc),
                )
            ],
        )

    if total_pages == 0:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="EMPTY_PDF",
            issues=[
                _issue(
                    "PDF_HAS_NO_PAGES",
                    "The uploaded PDF contains no pages.",
                )
            ],
        )

    if total_pages > max_pages:
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="DOCUMENT_LIMIT_EXCEEDED",
            total_pages=total_pages,
            issues=[
                _issue(
                    "PDF_PAGE_LIMIT_EXCEEDED",
                    "The uploaded PDF exceeds the configured page limit.",
                )
            ],
        )

    pages: list[PdfPageText] = []
    issues: list[PdfIngestionIssue] = []
    extracted_character_count = 0
    vision_candidate_page_numbers: list[int] = []

    # -----------------------------------------------------
    # PASS 1 — Embedded PDF text only.
    #
    # No Vision calls are permitted in this pass. This lets
    # us know the complete number of pages that would require
    # Vision before spending API calls.
    # -----------------------------------------------------
    for page_number, page in enumerate(
        reader.pages,
        start=1,
    ):
        try:
            extracted = page.extract_text() or ""
        except Exception as exc:
            return _failed_document(
                role=role,
                filename=safe_filename,
                raw_bytes=raw_bytes,
                content_sha256=content_hash,
                status="PDF_EXTRACTION_FAILED",
                total_pages=total_pages,
                pages=pages,
                issues=[
                    _issue(
                        "PDF_PAGE_TEXT_EXTRACTION_FAILED",
                        f"Page {page_number} text extraction failed: {exc}",
                    )
                ],
            )

        page_text = (
            extracted.replace(
                "\r\n",
                "\n",
            )
            .replace(
                "\r",
                "\n",
            )
            .strip()
        )

        extracted_character_count += len(page_text)

        if extracted_character_count > max_extracted_characters:
            return _failed_document(
                role=role,
                filename=safe_filename,
                raw_bytes=raw_bytes,
                content_sha256=content_hash,
                status="DOCUMENT_LIMIT_EXCEEDED",
                total_pages=total_pages,
                pages=pages,
                issues=[
                    _issue(
                        "PDF_TEXT_LIMIT_EXCEEDED",
                        "Extracted PDF text exceeds the configured limit.",
                    )
                ],
            )

        pages.append(
            PdfPageText(
                page_number=page_number,
                text=page_text,
                text_sha256=sha256(
                    page_text.encode("utf-8")
                ).hexdigest(),
            )
        )

        if not page_text:
            vision_candidate_page_numbers.append(
                page_number
            )

    # -----------------------------------------------------
    # Resolve explicit selected-page scope.
    #
    # When no explicit scope is supplied, the existing behavior remains:
    # every Vision candidate must fit within the automatic page budget.
    #
    # When an explicit scope is supplied, only that validated subset is
    # eligible for Vision processing.
    # -----------------------------------------------------
    explicit_vision_selection = (
        vision_page_numbers is not None
    )

    if explicit_vision_selection:
        raw_selection = tuple(
            vision_page_numbers or ()
        )

        selection_invalid = (
            any(
                isinstance(page_number, bool)
                or not isinstance(page_number, int)
                for page_number in raw_selection
            )
            or len(raw_selection) != len(set(raw_selection))
            or len(raw_selection) > max_vision_pages
            or (
                bool(vision_candidate_page_numbers)
                and not raw_selection
            )
            or any(
                page_number
                not in set(vision_candidate_page_numbers)
                for page_number in raw_selection
            )
        )

        if selection_invalid:
            return _failed_document(
                role=role,
                filename=safe_filename,
                raw_bytes=raw_bytes,
                content_sha256=content_hash,
                status="VISION_PAGE_SELECTION_INVALID",
                total_pages=total_pages,
                pages=pages,
                issues=[
                    _issue(
                        "PDF_VISION_PAGE_SELECTION_INVALID",
                        (
                            "The selected Vision page scope is invalid. "
                            "Selected pages must be unique Vision "
                            "candidates and must not exceed the "
                            f"{max_vision_pages}-page budget."
                        ),
                    )
                ],
                vision_unprocessed_candidate_page_numbers=(
                    vision_candidate_page_numbers
                ),
            )

        selected_vision_page_numbers = tuple(
            sorted(raw_selection)
        )
    else:
        selected_vision_page_numbers = tuple(
            vision_candidate_page_numbers
        )

    if (
        vision_page_extractor is not None
        and not explicit_vision_selection
        and len(vision_candidate_page_numbers)
        > max_vision_pages
    ):
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="VISION_PAGE_BUDGET_EXCEEDED",
            total_pages=total_pages,
            pages=pages,
            issues=[
                _issue(
                    "PDF_VISION_PAGE_BUDGET_EXCEEDED",
                    (
                        "PDF requires Vision processing for "
                        f"{len(vision_candidate_page_numbers)} page(s), "
                        "which exceeds the automatic Vision budget of "
                        f"{max_vision_pages} page(s). "
                        "No Vision API calls were made."
                    ),
                )
            ],
            vision_unprocessed_candidate_page_numbers=(
                vision_candidate_page_numbers
            ),
        )

    if (
        explicit_vision_selection
        and selected_vision_page_numbers
        and vision_page_extractor is None
    ):
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="VISION_PAGE_SELECTION_INVALID",
            total_pages=total_pages,
            pages=pages,
            issues=[
                _issue(
                    "PDF_VISION_PAGE_EXTRACTOR_REQUIRED",
                    (
                        "A Vision page extractor is required when an "
                        "explicit Vision page scope is supplied."
                    ),
                )
            ],
            vision_unprocessed_candidate_page_numbers=(
                vision_candidate_page_numbers
            ),
        )

    # -----------------------------------------------------
    # PASS 2 — Vision only for the validated selected scope.
    # -----------------------------------------------------
    vision_processed_page_numbers: list[int] = []

    if vision_page_extractor is not None:
        for page_number in selected_vision_page_numbers:
            try:
                vision_extracted = (
                    vision_page_extractor(
                        raw_bytes,
                        page_number,
                    )
                    or ""
                )
            except Exception as exc:
                issues.append(
                    _issue(
                        "PDF_PAGE_VISION_FAILED",
                        (
                            f"Page {page_number} Vision extraction "
                            f"failed: {exc}"
                        ),
                        severity="WARNING",
                    )
                )
                continue

            vision_page_text = (
                vision_extracted.replace(
                    "\r\n",
                    "\n",
                )
                .replace(
                    "\r",
                    "\n",
                )
                .strip()
            )

            if not vision_page_text:
                continue

            extracted_character_count += len(
                vision_page_text
            )

            if (
                extracted_character_count
                > max_extracted_characters
            ):
                return _failed_document(
                    role=role,
                    filename=safe_filename,
                    raw_bytes=raw_bytes,
                    content_sha256=content_hash,
                    status="DOCUMENT_LIMIT_EXCEEDED",
                    total_pages=total_pages,
                    pages=pages,
                    issues=[
                        *issues,
                        _issue(
                            "PDF_TEXT_LIMIT_EXCEEDED",
                            (
                                "Extracted PDF text exceeds "
                                "the configured limit."
                            ),
                        ),
                    ],
                    vision_processed_page_numbers=(
                        vision_processed_page_numbers
                    ),
                    vision_unprocessed_candidate_page_numbers=tuple(
                        page_number
                        for page_number
                        in vision_candidate_page_numbers
                        if page_number
                        not in vision_processed_page_numbers
                    ),
                )

            pages[page_number - 1] = PdfPageText(
                page_number=page_number,
                text=vision_page_text,
                text_sha256=sha256(
                    vision_page_text.encode("utf-8")
                ).hexdigest(),
            )

            vision_processed_page_numbers.append(
                page_number
            )

            issues.append(
                _issue(
                    "PDF_PAGE_VISION_USED",
                    (
                        f"Page {page_number} used "
                        "Vision fallback because embedded "
                        "PDF text was unavailable."
                    ),
                    severity="WARNING",
                )
            )

    if explicit_vision_selection:
        incomplete_selected_pages = tuple(
            page_number
            for page_number
            in selected_vision_page_numbers
            if page_number
            not in vision_processed_page_numbers
        )

        if incomplete_selected_pages:
            return _failed_document(
                role=role,
                filename=safe_filename,
                raw_bytes=raw_bytes,
                content_sha256=content_hash,
                status="VISION_SELECTED_PAGE_EXTRACTION_INCOMPLETE",
                total_pages=total_pages,
                pages=pages,
                issues=[
                    *issues,
                    _issue(
                        "PDF_VISION_SELECTED_PAGE_EXTRACTION_INCOMPLETE",
                        (
                            "One or more explicitly selected Vision "
                            "pages did not produce usable text."
                        ),
                    ),
                ],
                vision_processed_page_numbers=(
                    vision_processed_page_numbers
                ),
                vision_unprocessed_candidate_page_numbers=tuple(
                    page_number
                    for page_number
                    in vision_candidate_page_numbers
                    if page_number
                    not in vision_processed_page_numbers
                ),
            )

    # Record any page that remains text-empty after the
    # optional Vision pass.
    for page_number in vision_candidate_page_numbers:
        if not pages[page_number - 1].text.strip():
            issues.append(
                _issue(
                    "PDF_PAGE_TEXT_EMPTY",
                    (
                        f"Page {page_number} contains "
                        "no extractable text."
                    ),
                    severity="WARNING",
                )
            )

    if not any(page.text.strip() for page in pages):
        return _failed_document(
            role=role,
            filename=safe_filename,
            raw_bytes=raw_bytes,
            content_sha256=content_hash,
            status="IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED",
            total_pages=total_pages,
            pages=pages,
            issues=[
                *issues,
                _issue(
                    "PDF_TEXT_NOT_EXTRACTABLE",
                    (
                        "No usable text could be extracted from the PDF "
                        "pages."
                    ),
                ),
            ],
        )

    vision_unprocessed_candidate_page_numbers = tuple(
        page_number
        for page_number in vision_candidate_page_numbers
        if page_number not in vision_processed_page_numbers
    )

    if (
        explicit_vision_selection
        and vision_unprocessed_candidate_page_numbers
    ):
        final_status = "READY_FOR_SELECTED_PAGE_ANALYSIS"

        issues.append(
            _issue(
                "PDF_VISION_SELECTED_PAGE_SCOPE_USED",
                (
                    "Semantic analysis is limited to the explicitly "
                    "selected Vision page scope. Unprocessed Vision "
                    "candidate pages remain outside the analyzed scope."
                ),
                severity="WARNING",
            )
        )
    else:
        final_status = "READY_FOR_SEMANTIC_ANALYSIS"

    return IngestedPdfDocument(
        role=role,
        filename=safe_filename,
        content_sha256=content_hash,
        raw_bytes=raw_bytes,
        total_pages=total_pages,
        pages=tuple(pages),
        status=final_status,
        issues=tuple(issues),
        vision_processed_page_numbers=tuple(
            vision_processed_page_numbers
        ),
        vision_unprocessed_candidate_page_numbers=(
            vision_unprocessed_candidate_page_numbers
        ),
    )



def pdf_document_requires_vision(
    document: IngestedPdfDocument,
) -> bool:
    """
    Return True when at least one parsed PDF page has no usable text.

    A mixed PDF can already be READY_FOR_SEMANTIC_ANALYSIS while still
    containing image-only pages, so document status alone is not enough.
    """

    if not document.pages:
        return False

    return any(
        not page.text.strip()
        for page in document.pages
    )


def pdf_document_can_attempt_vision(
    document: IngestedPdfDocument,
) -> bool:
    """
    Return True only for structurally readable PDFs whose pages may be
    revisited with Vision.

    Invalid, empty, encrypted, over-limit, or otherwise unreadable PDF
    containers are not promoted to Vision processing.
    """

    if not document.raw_bytes:
        return False

    if document.total_pages < 1:
        return False

    return document.status in {
        "READY_FOR_SEMANTIC_ANALYSIS",
        "IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED",
    }


def prepare_pdf_document_for_semantic_analysis(
    document: IngestedPdfDocument,
    *,
    vision_page_extractor: VisionPageExtractor,
) -> IngestedPdfDocument:
    """
    Re-ingest only when the PDF has pages that need Vision recovery.

    Embedded-text pages continue through the existing pypdf path.
    The supplied Vision extractor is invoked only for pages whose
    embedded text is empty.
    """

    if not pdf_document_can_attempt_vision(document):
        return document

    if not pdf_document_requires_vision(document):
        return document

    return ingest_pdf_document(
        role=document.role,
        filename=document.filename,
        content=document.raw_bytes,
        vision_page_extractor=vision_page_extractor,
    )


def validate_pdf_document_set(
    documents: Sequence[IngestedPdfDocument],
) -> PdfDocumentSetValidation:
    """Validate duplicate identities without conflating source roles."""

    issues: list[PdfIngestionIssue] = []
    seen_role_hashes: set[tuple[str, str]] = set()
    roles_by_hash: dict[str, set[str]] = {}

    for document in documents:
        if not document.ready_for_semantic_analysis:
            issues.append(
                _issue(
                    "PDF_DOCUMENT_NOT_READY",
                    f"{document.role} PDF is not ready for semantic analysis.",
                )
            )

        role_hash = (
            document.role,
            document.content_sha256,
        )

        if role_hash in seen_role_hashes:
            issues.append(
                _issue(
                    "DUPLICATE_PDF_IN_ROLE",
                    "The same PDF was supplied more than once for the "
                    f"{document.role} role.",
                )
            )
        else:
            seen_role_hashes.add(role_hash)

        roles_by_hash.setdefault(
            document.content_sha256,
            set(),
        ).add(document.role)

    for roles in roles_by_hash.values():
        if len(roles) > 1:
            issues.append(
                _issue(
                    "PDF_REUSED_ACROSS_ROLES",
                    "The same PDF is being analyzed separately across "
                    "multiple document roles. Role provenance will "
                    "remain distinct.",
                    severity="WARNING",
                )
            )

    if any(issue.severity == "ERROR" for issue in issues):
        status = "PDF_DOCUMENT_SET_BLOCKED"
    elif issues:
        status = "PDF_DOCUMENT_SET_READY_WITH_WARNINGS"
    else:
        status = "PDF_DOCUMENT_SET_READY"

    return PdfDocumentSetValidation(
        status=status,
        issues=tuple(issues),
    )


def build_page_aware_text(
    document: IngestedPdfDocument,
) -> str:
    if not document.ready_for_semantic_analysis:
        raise ValueError(
            "PDF document is not ready for semantic analysis."
        )

    blocks = []

    for page in document.pages:
        blocks.append(
            f"===== PDF PAGE {page.page_number} =====\n"
            + page.text
        )

    return "\n\n".join(blocks)


def build_semantic_document(
    document: IngestedPdfDocument,
) -> SemanticDocument:
    if document.role not in {
        "requirement",
        "verification",
    }:
        raise ValueError(
            "Only requirement or verification PDFs can be "
            "converted to SemanticDocument."
        )

    return SemanticDocument(
        role=document.role,
        source_name=document.filename,
        text=build_page_aware_text(document),
        source_sha256=document.content_sha256,
        source_pages=tuple(
            SemanticSourcePage(
                page_number=page.page_number,
                text=page.text,
            )
            for page in document.pages
        ),
        source_format="pdf",
        analysis_scope=(
            "FULL_DOCUMENT"
            if document.full_document_coverage
            else "SELECTED_PAGES"
        ),
        vision_processed_page_numbers=(
            document.vision_processed_page_numbers
        ),
        vision_unprocessed_candidate_page_numbers=(
            document.vision_unprocessed_candidate_page_numbers
        ),
    )


def build_pdf_page_preview(
    document: IngestedPdfDocument,
    page_number: int,
) -> bytes:
    """Return a one-page PDF containing the selected original page."""

    if page_number < 1 or page_number > document.total_pages:
        raise ValueError(
            "PDF preview page is outside the document page range."
        )

    reader = PdfReader(
        BytesIO(document.raw_bytes),
        strict=False,
    )

    if reader.is_encrypted:
        raise ValueError(
            "Encrypted PDF preview is not supported."
        )

    writer = PdfWriter()
    writer.add_page(reader.pages[page_number - 1])
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
