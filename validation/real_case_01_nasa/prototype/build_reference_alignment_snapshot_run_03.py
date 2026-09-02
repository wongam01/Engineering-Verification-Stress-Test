from __future__ import annotations

import hashlib
import json

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

NASA_DIR = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
)

PROTOTYPE_DIR = (
    NASA_DIR
    / "prototype"
)

REFERENCE_DIR = (
    NASA_DIR
    / "reference"
)

RUN_03_FILE = (
    PROTOTYPE_DIR
    / "blind_ai_extract_run_03.json"
)

REFERENCE_FILE = (
    REFERENCE_DIR
    / "reference_v1.json"
)

OUTPUT_FILE = (
    PROTOTYPE_DIR
    / "run_03_vs_frozen_reference_snapshot.json"
)

TARGET_IDS = tuple(
    f"NCPR {number}"
    for number in range(18, 30)
)


def sha256_file(
    path: Path,
) -> str:

    hasher = hashlib.sha256()

    with path.open("rb") as file:
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


def load_json(
    path: Path,
) -> dict:

    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n"
            f"{path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def summarize_prototype_item(
    item: dict,
) -> dict:

    return {
        "source_line_id":
            item.get("source_line_id"),

        "constraint_id":
            item.get("constraint_id"),

        "type":
            item.get("type"),

        "unit":
            item.get("unit"),

        "variable":
            item.get("variable"),

        "min":
            item.get("min"),

        "max":
            item.get("max"),

        "left":
            item.get("left"),

        "right":
            item.get("right"),

        "variables":
            item.get("variables"),

        "limit":
            item.get("limit"),

        "needs_review":
            item.get("needs_review"),

        "review_reason":
            item.get("review_reason"),

        "source_text":
            item.get("source_text"),
    }


def main() -> None:

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Reference alignment snapshot "
            "will not be overwritten."
        )

    run2 = load_json(
        RUN_03_FILE
    )

    reference = load_json(
        REFERENCE_FILE
    )

    # =====================================================
    # Frozen Reference metadata 확인
    # =====================================================

    reference_metadata = (
        reference.get(
            "reference_metadata",
            {}
        )
    )

    reference_status = (
        reference_metadata.get(
            "status"
        )
    )

    reference_id = (
        reference_metadata.get(
            "reference_id"
        )
    )

    # metadata key 이름이 달라도
    # reference body는 그대로 보존하므로
    # 여기서는 강제로 추측하지 않는다.

    # =====================================================
    # Prototype grouping
    # =====================================================

    prototype_grouped = (
        defaultdict(list)
    )

    for item in run2.get(
        "constraints",
        [],
    ):

        requirement_id = (
            item.get(
                "constraint_id"
            )
        )

        if requirement_id in TARGET_IDS:

            prototype_grouped[
                requirement_id
            ].append(
                summarize_prototype_item(
                    item
                )
            )

    # =====================================================
    # Reference grouping
    # =====================================================

    reference_requirements = (
        reference.get(
            "requirements",
            []
        )
    )

    reference_grouped = {}

    for requirement in (
        reference_requirements
    ):

        requirement_id = (
            requirement.get(
                "requirement_id"
            )
        )

        if requirement_id in TARGET_IDS:

            reference_grouped[
                requirement_id
            ] = requirement

    # =====================================================
    # Target completeness
    # =====================================================

    missing_reference_ids = [
        requirement_id
        for requirement_id
        in TARGET_IDS
        if requirement_id
        not in reference_grouped
    ]

    missing_prototype_ids = [
        requirement_id
        for requirement_id
        in TARGET_IDS
        if not prototype_grouped.get(
            requirement_id
        )
    ]

    if missing_reference_ids:
        raise RuntimeError(
            "Frozen Reference is missing "
            "target IDs: "
            f"{missing_reference_ids}"
        )

    # =====================================================
    # Side-by-side snapshot
    # =====================================================

    alignments = []

    for requirement_id in TARGET_IDS:

        frozen = (
            reference_grouped[
                requirement_id
            ]
        )

        prototype_items = (
            prototype_grouped.get(
                requirement_id,
                []
            )
        )

        alignments.append(
            {
                "requirement_id":
                    requirement_id,

                "frozen_reference": {
                    "source_location":
                        frozen.get(
                            "source_location"
                        ),

                    "source_excerpt":
                        frozen.get(
                            "source_excerpt"
                        ),

                    "engineering_meaning":
                        frozen.get(
                            "engineering_meaning"
                        ),

                    "semantic_categories":
                        frozen.get(
                            "semantic_categories"
                        ),

                    "normalized_constraints":
                        frozen.get(
                            "normalized_constraints"
                        ),

                    "coverage_or_condition":
                        frozen.get(
                            "coverage_or_condition"
                        ),

                    "reference_status":
                        frozen.get(
                            "reference_status"
                        ),
                },

                "prototype_run_03": {
                    "constraint_count":
                        len(
                            prototype_items
                        ),

                    "types": [
                        item.get(
                            "type"
                        )
                        for item
                        in prototype_items
                    ],

                    "needs_review": [
                        item.get(
                            "needs_review"
                        )
                        for item
                        in prototype_items
                    ],

                    "constraints":
                        prototype_items,
                },

                # 중요:
                # 여기서는 correctness를
                # 자동 판정하지 않는다.
                "evaluation": {
                    "status":
                        "NOT_JUDGED",

                    "notes":
                        None,
                },
            }
        )

    artifact = {
        "metadata": {
            "stage": (
                "RUN_03_VS_FROZEN_REFERENCE_"
                "ALIGNMENT_SNAPSHOT"
            ),

            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "run_03_file": str(
                RUN_03_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),

            "run_03_sha256":
                sha256_file(
                    RUN_03_FILE
                ),

            "frozen_reference_file": str(
                REFERENCE_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),

            "frozen_reference_sha256":
                sha256_file(
                    REFERENCE_FILE
                ),

            "reference_id":
                reference_id,

            "reference_status":
                reference_status,

            "target_ids":
                list(
                    TARGET_IDS
                ),

            "semantic_correctness_judged":
                False,

            "automatic_pass_fail_used":
                False,
        },

        "completeness": {
            "target_requirement_count":
                len(TARGET_IDS),

            "reference_found_count":
                len(
                    reference_grouped
                ),

            "prototype_found_count":
                sum(
                    1
                    for requirement_id
                    in TARGET_IDS
                    if prototype_grouped.get(
                        requirement_id
                    )
                ),

            "missing_reference_ids":
                missing_reference_ids,

            "missing_prototype_ids":
                missing_prototype_ids,
        },

        "alignments":
            alignments,
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
        "=== RUN #2 VS FROZEN REFERENCE SNAPSHOT ==="
    )
    print()

    print(
        "Target requirements: "
        f"{len(TARGET_IDS)}"
    )

    print(
        "Reference IDs found: "
        f"{len(reference_grouped)}"
    )

    print(
        "Prototype IDs found: "
        f"{artifact['completeness']['prototype_found_count']}"
    )

    print()

    print(
        "=== ALIGNMENT PREVIEW ==="
    )

    for item in alignments:

        frozen = (
            item[
                "frozen_reference"
            ]
        )

        prototype = (
            item[
                "prototype_run_03"
            ]
        )

        print(
            f"{item['requirement_id']} | "
            f"types={prototype['types']} | "
            f"review={prototype['needs_review']}"
        )

        print(
            "  Reference categories: "
            f"{frozen['semantic_categories']}"
        )

        print(
            "  Reference normalized: "
            f"{frozen['normalized_constraints']}"
        )

        print()

    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print()

    print(
        "No automatic correctness judgment "
        "was made."
    )


if __name__ == "__main__":
    main()