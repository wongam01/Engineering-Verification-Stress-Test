from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

SNAPSHOT_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "run_02_vs_frozen_reference_snapshot.json"
)

TARGET_IDS = tuple(
    f"NCPR {number}"
    for number in range(18, 30)
)


def load_snapshot() -> dict:
    if not SNAPSHOT_FILE.exists():
        raise FileNotFoundError(
            f"Snapshot not found:\n"
            f"{SNAPSHOT_FILE}"
        )

    return json.loads(
        SNAPSHOT_FILE.read_text(
            encoding="utf-8"
        )
    )


def print_json_value(
    label: str,
    value,
) -> None:
    print(
        f"{label}: "
        f"{json.dumps(value, ensure_ascii=False)}"
    )


def main() -> None:
    snapshot = load_snapshot()

    alignments = {
        item["requirement_id"]: item
        for item in snapshot.get(
            "alignments",
            [],
        )
    }

    missing = [
        requirement_id
        for requirement_id in TARGET_IDS
        if requirement_id not in alignments
    ]

    if missing:
        raise RuntimeError(
            "Snapshot is missing target IDs: "
            f"{missing}"
        )

    print(
        "=== NASA RUN #2 FINAL "
        "ADJUDICATION EVIDENCE ==="
    )
    print()

    print(
        "This script does NOT make "
        "correctness judgments."
    )
    print(
        "It only displays Frozen Reference "
        "and Prototype Run #2 evidence."
    )
    print()

    for requirement_id in TARGET_IDS:
        item = alignments[
            requirement_id
        ]

        frozen = item[
            "frozen_reference"
        ]

        prototype = item[
            "prototype_run_02"
        ]

        print(
            "=" * 72
        )
        print(
            requirement_id
        )
        print(
            "=" * 72
        )

        print()
        print(
            "[FROZEN REFERENCE]"
        )

        print_json_value(
            "Source location",
            frozen.get(
                "source_location"
            ),
        )

        print_json_value(
            "Source excerpt",
            frozen.get(
                "source_excerpt"
            ),
        )

        print_json_value(
            "Engineering meaning",
            frozen.get(
                "engineering_meaning"
            ),
        )

        print_json_value(
            "Semantic categories",
            frozen.get(
                "semantic_categories"
            ),
        )

        print_json_value(
            "Normalized constraints",
            frozen.get(
                "normalized_constraints"
            ),
        )

        print_json_value(
            "Coverage / condition",
            frozen.get(
                "coverage_or_condition"
            ),
        )

        print_json_value(
            "Reference status",
            frozen.get(
                "reference_status"
            ),
        )

        print()
        print(
            "[PROTOTYPE RUN #2]"
        )

        print(
            "Constraint count: "
            f"{prototype.get('constraint_count')}"
        )

        print_json_value(
            "Types",
            prototype.get(
                "types"
            ),
        )

        print_json_value(
            "Needs review",
            prototype.get(
                "needs_review"
            ),
        )

        constraints = prototype.get(
            "constraints",
            [],
        )

        for index, constraint in enumerate(
            constraints,
            start=1,
        ):
            print()
            print(
                f"  Prototype constraint #{index}"
            )

            fields = [
                "source_line_id",
                "constraint_id",
                "type",
                "unit",
                "variable",
                "min",
                "max",
                "left",
                "right",
                "variables",
                "limit",
                "needs_review",
                "review_reason",
                "source_text",
            ]

            for field_name in fields:
                print_json_value(
                    f"    {field_name}",
                    constraint.get(
                        field_name
                    ),
                )

        print()

    print(
        "=" * 72
    )
    print(
        "END OF ADJUDICATION EVIDENCE"
    )
    print(
        "=" * 72
    )


if __name__ == "__main__":
    main()