from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.ai.multi_constraint_parser import (
    extract_constraints_from_document,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SOURCE_TEXT_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_source_text_run_03.txt"
)

PREPROCESS_RESULT_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_preprocess_run_04.json"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_ai_extract_run_03.json"
)


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            hasher.update(chunk)

    return hasher.hexdigest()


def main() -> None:
    if not SOURCE_TEXT_FILE.exists():
        raise FileNotFoundError(
            f"Blind source text not found:\n"
            f"{SOURCE_TEXT_FILE}"
        )

    if not PREPROCESS_RESULT_FILE.exists():
        raise FileNotFoundError(
            f"Preprocess result not found:\n"
            f"{PREPROCESS_RESULT_FILE}"
        )

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Blind AI Extraction Run #3 will not be overwritten."
        )

    source_text = SOURCE_TEXT_FILE.read_text(
        encoding="utf-8"
    )

    source_text_sha256 = sha256_file(
        SOURCE_TEXT_FILE
    )

    preprocess_sha256 = sha256_file(
        PREPROCESS_RESULT_FILE
    )

    print(
        "=== PROTOTYPE BLIND AI EXTRACTION RUN #3 ==="
    )
    print(
        "Running existing general document parser..."
    )
    print(
        "No frozen reference is being read."
    )
    print(
        "No target NCPR IDs are being supplied to the AI."
    )
    print()

    extracted = extract_constraints_from_document(
        text=source_text,
        constraint_role="requirement",
        source_name=(
            "NASA-SPEC-5022 Change 2 "
            "Revalidated 2026 pages 15-16"
        ),
    )

    type_counts = Counter(
        item.get("type", "MISSING")
        for item in extracted
    )

    review_count = sum(
        1
        for item in extracted
        if item.get("needs_review") is True
    )

    artifact = {
        "metadata": {
            "stage": (
                "PROTOTYPE_BLIND_AI_EXTRACTION_RUN_03"
            ),
            "created_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "model": "gpt-5.6-terra",
            "source_text_file": str(
                SOURCE_TEXT_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "source_text_sha256": (
                source_text_sha256
            ),
            "preprocess_result_file": str(
                PREPROCESS_RESULT_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "preprocess_result_sha256": (
                preprocess_sha256
            ),
            "constraint_role": "requirement",
            "reference_file_used": False,
            "expected_result_used": False,
            "target_ncpr_ids_supplied_to_ai": False,
            "prototype_nasa_specific_prompt_used": False,
        },
        "summary": {
            "extracted_count": len(
                extracted
            ),
            "type_counts": dict(
                sorted(type_counts.items())
            ),
            "needs_review_count": review_count,
        },
        "constraints": extracted,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            artifact,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        f"Extracted constraints: {len(extracted)}"
    )
    print(
        f"Type counts: {dict(type_counts)}"
    )
    print(
        f"Needs review: {review_count}"
    )
    print()

    print(
        "=== EXTRACTION PREVIEW ==="
    )

    for index, item in enumerate(
        extracted,
        start=1,
    ):
        print(
            f"{index:02d}. "
            f"{item.get('constraint_id')} | "
            f"{item.get('type')} | "
            f"review={item.get('needs_review')} | "
            f"source={item.get('source_line_id')}"
        )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print()
    print(
        "Blind AI Extraction Run #3 completed."
    )
    print(
        "Do NOT overwrite this post-fix retest artifact."
    )


if __name__ == "__main__":
    main()