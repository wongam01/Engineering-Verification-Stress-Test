from __future__ import annotations

import hashlib
import json

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

PROTOTYPE_DIR = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
)

RUN_01_FILE = (
    PROTOTYPE_DIR
    / "blind_ai_extract_run_01.json"
)

RUN_02_FILE = (
    PROTOTYPE_DIR
    / "blind_ai_extract_run_02.json"
)

OUTPUT_FILE = (
    PROTOTYPE_DIR
    / "blind_run_01_vs_02_comparison.json"
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
            hasher.update(chunk)

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


def group_constraints(
    artifact: dict,
) -> dict[str, list[dict]]:

    grouped = defaultdict(list)

    for item in artifact.get(
        "constraints",
        [],
    ):
        constraint_id = item.get(
            "constraint_id"
        )

        if constraint_id in TARGET_IDS:
            grouped[
                constraint_id
            ].append(item)

    return {
        requirement_id: grouped.get(
            requirement_id,
            [],
        )
        for requirement_id
        in TARGET_IDS
    }


def type_counts_for_targets(
    grouped: dict[str, list[dict]],
) -> dict[str, int]:

    counter = Counter()

    for items in grouped.values():
        for item in items:
            counter[
                item.get(
                    "type",
                    "MISSING",
                )
            ] += 1

    return dict(
        sorted(
            counter.items()
        )
    )


def summarize_item(
    item: dict,
) -> dict:

    return {
        "source_line_id": item.get(
            "source_line_id"
        ),
        "constraint_id": item.get(
            "constraint_id"
        ),
        "type": item.get(
            "type"
        ),
        "unit": item.get(
            "unit"
        ),
        "variable": item.get(
            "variable"
        ),
        "min": item.get(
            "min"
        ),
        "max": item.get(
            "max"
        ),
        "left": item.get(
            "left"
        ),
        "right": item.get(
            "right"
        ),
        "variables": item.get(
            "variables"
        ),
        "limit": item.get(
            "limit"
        ),
        "needs_review": item.get(
            "needs_review"
        ),
        "review_reason": item.get(
            "review_reason"
        ),
        "source_text": item.get(
            "source_text"
        ),
    }


def main() -> None:

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Comparison artifact will not "
            "be overwritten."
        )

    run1 = load_json(
        RUN_01_FILE
    )

    run2 = load_json(
        RUN_02_FILE
    )

    metadata1 = run1["metadata"]
    metadata2 = run2["metadata"]

    equivalence_checks = {
        "same_source_text_file": (
            metadata1[
                "source_text_file"
            ]
            == metadata2[
                "source_text_file"
            ]
        ),
        "same_source_text_sha256": (
            metadata1[
                "source_text_sha256"
            ]
            == metadata2[
                "source_text_sha256"
            ]
        ),
        "same_preprocess_result_file": (
            metadata1[
                "preprocess_result_file"
            ]
            == metadata2[
                "preprocess_result_file"
            ]
        ),
        "same_preprocess_result_sha256": (
            metadata1[
                "preprocess_result_sha256"
            ]
            == metadata2[
                "preprocess_result_sha256"
            ]
        ),
    }

    if not all(
        equivalence_checks.values()
    ):
        raise RuntimeError(
            "Run #1 / Run #2 input "
            "equivalence check failed."
        )

    run1_grouped = (
        group_constraints(
            run1
        )
    )

    run2_grouped = (
        group_constraints(
            run2
        )
    )

    comparison = []

    for requirement_id in TARGET_IDS:

        run1_items = [
            summarize_item(item)
            for item
            in run1_grouped[
                requirement_id
            ]
        ]

        run2_items = [
            summarize_item(item)
            for item
            in run2_grouped[
                requirement_id
            ]
        ]

        comparison.append(
            {
                "requirement_id":
                    requirement_id,

                "run_01_count":
                    len(run1_items),

                "run_02_count":
                    len(run2_items),

                "run_01_types": [
                    item["type"]
                    for item
                    in run1_items
                ],

                "run_02_types": [
                    item["type"]
                    for item
                    in run2_items
                ],

                "run_01_needs_review": [
                    item[
                        "needs_review"
                    ]
                    for item
                    in run1_items
                ],

                "run_02_needs_review": [
                    item[
                        "needs_review"
                    ]
                    for item
                    in run2_items
                ],

                "run_01_constraints":
                    run1_items,

                "run_02_constraints":
                    run2_items,
            }
        )

    artifact = {
        "metadata": {
            "stage": (
                "PROTOTYPE_BLIND_RUN_01_"
                "VS_RUN_02_COMPARISON"
            ),
            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "run_01_file": str(
                RUN_01_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "run_01_sha256": (
                sha256_file(
                    RUN_01_FILE
                )
            ),
            "run_02_file": str(
                RUN_02_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "run_02_sha256": (
                sha256_file(
                    RUN_02_FILE
                )
            ),
            "target_ids": list(
                TARGET_IDS
            ),
            "frozen_reference_used":
                False,
            "semantic_correctness_judged":
                False,
        },

        "input_equivalence_checks":
            equivalence_checks,

        "target_summary": {
            "target_requirement_count":
                len(TARGET_IDS),

            "run_01_found_requirement_count":
                sum(
                    1
                    for items
                    in run1_grouped.values()
                    if items
                ),

            "run_02_found_requirement_count":
                sum(
                    1
                    for items
                    in run2_grouped.values()
                    if items
                ),

            "run_01_extracted_constraint_count":
                sum(
                    len(items)
                    for items
                    in run1_grouped.values()
                ),

            "run_02_extracted_constraint_count":
                sum(
                    len(items)
                    for items
                    in run2_grouped.values()
                ),

            "run_01_type_counts":
                type_counts_for_targets(
                    run1_grouped
                ),

            "run_02_type_counts":
                type_counts_for_targets(
                    run2_grouped
                ),
        },

        "requirements":
            comparison,
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
        "=== BLIND RUN #1 VS RUN #2 ==="
    )
    print()

    summary = artifact[
        "target_summary"
    ]

    print(
        "Target requirements: "
        f"{summary['target_requirement_count']}"
    )

    print(
        "Run #1 found IDs: "
        f"{summary['run_01_found_requirement_count']}"
    )

    print(
        "Run #2 found IDs: "
        f"{summary['run_02_found_requirement_count']}"
    )

    print(
        "Run #1 target constraints: "
        f"{summary['run_01_extracted_constraint_count']}"
    )

    print(
        "Run #2 target constraints: "
        f"{summary['run_02_extracted_constraint_count']}"
    )

    print(
        "Run #1 target types: "
        f"{summary['run_01_type_counts']}"
    )

    print(
        "Run #2 target types: "
        f"{summary['run_02_type_counts']}"
    )

    print()
    print(
        "=== REQUIREMENT TYPE CHANGES ==="
    )

    for item in comparison:
        print(
            f"{item['requirement_id']}: "
            f"{item['run_01_types']} "
            f"-> "
            f"{item['run_02_types']}"
        )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print()
    print(
        "No Frozen Reference was used "
        "for this comparison."
    )
    print(
        "No semantic correctness "
        "judgment was made."
    )


if __name__ == "__main__":
    main()