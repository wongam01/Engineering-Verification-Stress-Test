from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from src.ai.multi_constraint_parser import (
    prepare_document_lines,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SOURCE_PDF = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "source"
    / "NASA-SPEC-5022_Change2_Revalidated_2026.pdf"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
)

RAW_TEXT_FILE = (
    OUTPUT_DIR
    / "blind_source_text_run_02.txt"
)

PREPROCESS_FILE = (
    OUTPUT_DIR
    / "blind_preprocess_run_02.json"
)


# Reference benchmark에서 선택한 source scope와 동일한
# PDF physical page 범위만 사용한다.
#
# IMPORTANT:
# 이 값은 expected result가 아니라
# 평가할 source document 범위다.
PDF_PAGES = [
    15,
    16,
]


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            hasher.update(chunk)

    return hasher.hexdigest()


def extract_pdf_text(
    pdf_path: Path,
    page_numbers: list[int],
) -> str:
    reader = PdfReader(pdf_path)

    extracted_pages = []

    for page_number in page_numbers:
        page_index = page_number - 1

        if page_index < 0 or page_index >= len(reader.pages):
            raise ValueError(
                f"PDF page out of range: {page_number}"
            )

        text = reader.pages[
            page_index
        ].extract_text()

        if text is None:
            text = ""

        extracted_pages.append(
            (
                f"\n"
                f"===== PDF PAGE {page_number} =====\n"
                f"{text.strip()}\n"
            )
        )

    return "\n".join(extracted_pages)


def main() -> None:
    if not SOURCE_PDF.exists():
        raise FileNotFoundError(
            f"NASA source PDF not found:\n{SOURCE_PDF}"
        )

    if RAW_TEXT_FILE.exists():
        raise FileExistsError(
            f"{RAW_TEXT_FILE.name} already exists.\n"
            "Blind Run #2 source text will not be overwritten."
        )

    if PREPROCESS_FILE.exists():
        raise FileExistsError(
            f"{PREPROCESS_FILE.name} already exists.\n"
            "Blind Run #2 preprocessing result will not be overwritten."
        )

    source_sha256 = sha256_file(
        SOURCE_PDF
    )

    raw_text = extract_pdf_text(
        SOURCE_PDF,
        PDF_PAGES,
    )

    RAW_TEXT_FILE.write_text(
        raw_text,
        encoding="utf-8",
    )

    (
        prepared_text,
        source_map,
    ) = prepare_document_lines(
        raw_text
    )

    artifact = {
        "metadata": {
            "stage": (
                "PROTOTYPE_BLIND_PREPROCESS_RUN_02"
            ),
            "created_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "source_file": str(
                SOURCE_PDF.relative_to(
                    PROJECT_ROOT
                )
            ),
            "source_sha256": source_sha256,
            "pdf_pages": PDF_PAGES,
            "reference_file_used": False,
            "expected_result_used": False,
            "prototype_modified_for_nasa": False,
        },
        "preprocessing": {
            "raw_character_count": len(
                raw_text
            ),
            "logical_block_count": len(
                source_map
            ),
            "prepared_text": prepared_text,
            "source_map": source_map,
        },
    }

    PREPROCESS_FILE.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        "=== PROTOTYPE BLIND PREPROCESS RUN #2 ==="
    )
    print(
        f"Source: {SOURCE_PDF.name}"
    )
    print(
        f"Source SHA-256: {source_sha256}"
    )
    print(
        f"PDF pages: {PDF_PAGES}"
    )
    print(
        f"Raw characters: {len(raw_text)}"
    )
    print(
        f"Logical blocks: {len(source_map)}"
    )
    print()

    print(
        "=== LOGICAL BLOCK PREVIEW ==="
    )

    for line_id, source_text in source_map.items():
        preview = " ".join(
            source_text.split()
        )

        if len(preview) > 220:
            preview = (
                preview[:220]
                + "..."
            )

        print(
            f"{line_id}: {preview}"
        )

    print()
    print(
        f"Raw text saved: {RAW_TEXT_FILE}"
    )
    print(
        f"Preprocess result saved: {PREPROCESS_FILE}"
    )
    print()
    print(
        "No AI extraction was executed."
    )
    print(
        "No frozen reference was read."
    )


if __name__ == "__main__":
    main()