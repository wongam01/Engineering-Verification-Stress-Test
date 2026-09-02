from __future__ import annotations

import hashlib
import json

from datetime import (
    datetime,
    timezone,
)
from pathlib import Path

from src.ai.multi_constraint_parser import (
    prepare_document_lines,
)


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

SOURCE_TEXT_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_source_text_run_03.txt"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_preprocess_run_04.json"
)


def sha256_file(
    path: Path,
) -> str:
    hasher = hashlib.sha256()

    with path.open(
        "rb"
    ) as file:
        for chunk in iter(
            lambda: file.read(
                1024 * 1024
            ),
            b"",
        ):
            hasher.update(
                chunk
            )

    return hasher.hexdigest()


def main() -> None:
    if not SOURCE_TEXT_FILE.exists():
        raise FileNotFoundError(
            "Frozen blind source text "
            "was not found:\n"
            f"{SOURCE_TEXT_FILE}"
        )

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} "
            "already exists.\n"
            "Preprocess Run #4 will "
            "not be overwritten."
        )

    source_text = (
        SOURCE_TEXT_FILE.read_text(
            encoding="utf-8"
        )
    )

    source_text_sha256 = (
        sha256_file(
            SOURCE_TEXT_FILE
        )
    )

    (
        prepared_text,
        source_map,
    ) = prepare_document_lines(
        source_text
    )

    artifact = {
        "metadata": {
            "stage": (
                "PROTOTYPE_BLIND_"
                "PREPROCESS_RUN_04"
            ),
            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "source_text_file": str(
                SOURCE_TEXT_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "source_text_sha256": (
                source_text_sha256
            ),
            "source_text_reused_from": (
                "BLIND_SOURCE_TEXT_RUN_03"
            ),
            "reference_file_used": False,
            "expected_result_used": False,
            "target_ids_used": False,
            "prototype_nasa_specific_rule_used": (
                False
            ),
            "purpose": (
                "Post-general-fix "
                "preprocessing evidence"
            ),
        },
        "preprocessing": {
            "raw_character_count": len(
                source_text
            ),
            "logical_block_count": len(
                source_map
            ),
            "prepared_text": (
                prepared_text
            ),
            "source_map": (
                source_map
            ),
        },
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
        "=== PROTOTYPE BLIND "
        "PREPROCESS RUN #4 ==="
    )

    print(
        "Frozen source:",
        SOURCE_TEXT_FILE.name,
    )

    print(
        "Source SHA-256:",
        source_text_sha256,
    )

    print(
        "Raw characters:",
        len(
            source_text
        ),
    )

    print(
        "Logical blocks:",
        len(
            source_map
        ),
    )

    print()

    print(
        "=== LOGICAL BLOCK PREVIEW ==="
    )

    for (
        line_id,
        source_text_block,
    ) in source_map.items():

        preview = " ".join(
            source_text_block.split()
        )

        if len(
            preview
        ) > 220:
            preview = (
                preview[:220]
                + "..."
            )

        print(
            f"{line_id}: "
            f"{preview}"
        )

    print()

    print(
        "No AI extraction was executed."
    )

    print(
        "No frozen reference was read."
    )

    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()