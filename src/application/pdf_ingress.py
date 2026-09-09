from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import Literal, Sequence

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

    @property
    def ready_for_semantic_analysis(self) -> bool:
        return self.status == "READY_FOR_SEMANTIC_ANALYSIS"

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


DEFAULT_MAX_PDF_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_PDF_PAGES = 200
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
) -> IngestedPdfDocument:
    """
    Read a text-based PDF without sending the PDF bytes to AI.

    Invalid, encrypted, image-only, and over-limit documents are
    returned as explicit fail-safe results. Text is never silently
    truncated.
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

        normalized_line_endings = extracted.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )

        page_text = normalized_line_endings.strip()
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

        if not page_text:
            issues.append(
                _issue(
                    "PDF_PAGE_TEXT_EMPTY",
                    f"Page {page_number} contains no extractable text.",
                    severity="WARNING",
                )
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
                _issue(
                    "PDF_TEXT_NOT_EXTRACTABLE",
                    "No extractable text was found. OCR and scanned PDFs "
                    "are not supported in Phase 5A.",
                )
            ],
        )

    return IngestedPdfDocument(
        role=role,
        filename=safe_filename,
        content_sha256=content_hash,
        raw_bytes=raw_bytes,
        total_pages=total_pages,
        pages=tuple(pages),
        status="READY_FOR_SEMANTIC_ANALYSIS",
        issues=tuple(issues),
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
