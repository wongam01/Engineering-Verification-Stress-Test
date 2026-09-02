from __future__ import annotations

import hashlib
import json
import re

from collections import Counter
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[3]
)

RUN_02_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_ai_extract_run_02.json"
)

RUN_03_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_ai_extract_run_03.json"
)

PREPROCESS_02_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "prototype"
    / "blind_preprocess_run_03.json"
)

PREPROCESS_03_FILE = (
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
    / "blind_run_02_vs_03_comparison.json"
)


TARGET_REQUIREMENT_IDS = [
    f"NCPR {number}"
    for number in range(
        18,
        30,
    )
]


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


def load_json(
    path: Path,
) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def normalize_constraint_id(
    value: Any,
) -> str:
    if value is None:
        return ""

    text = " ".join(
        str(value)
        .strip()
        .upper()
        .split()
    )

    match = re.fullmatch(
        r"NCPR\s*(\d+)",
        text,
    )

    if match:
        return (
            f"NCPR "
            f"{int(match.group(1))}"
        )

    return text


def get_source_map(
    preprocess_artifact: dict[str, Any],
) -> dict[str, str]:
    preprocessing = (
        preprocess_artifact.get(
            "preprocessing",
            {}
        )
    )

    source_map = (
        preprocessing.get(
            "source_map",
            {}
        )
    )

    if not isinstance(
        source_map,
        dict,
    ):
        raise ValueError(
            "preprocessing.source_map "
            "must be a dictionary."
        )

    return {
        str(key): str(value)
        for key, value
        in source_map.items()
    }


def get_constraints(
    artifact: dict[str, Any],
) -> list[dict[str, Any]]:
    constraints = artifact.get(
        "constraints",
        []
    )

    if not isinstance(
        constraints,
        list,
    ):
        raise ValueError(
            "constraints must be a list."
        )

    return constraints


def target_constraints(
    constraints: list[dict[str, Any]],
    requirement_id: str,
) -> list[dict[str, Any]]:
    return [
        item
        for item in constraints
        if normalize_constraint_id(
            item.get(
                "constraint_id"
            )
        )
        == requirement_id
    ]


def compact_constraint(
    item: dict[str, Any],
) -> dict[str, Any]:
    fields = [
        "constraint_id",
        "type",
        "variable",
        "unit",
        "min",
        "max",
        "left",
        "right",
        "variables",
        "limit",
        "needs_review",
        "review_reason",
        "source_line_id",
    ]

    return {
        field: item.get(
            field
        )
        for field in fields
    }


def claimed_id_marker(
    constraint_id: Any,
) -> str | None:
    normalized = (
        normalize_constraint_id(
            constraint_id
        )
    )

    match = re.fullmatch(
        r"NCPR\s+(\d+)",
        normalized,
    )

    if match is None:
        return None

    return (
        f"[NCPR "
        f"{int(match.group(1))}]"
    )


def attribution_check(
    item: dict[str, Any],
    source_map: dict[str, str],
) -> dict[str, Any]:
    source_line_id = item.get(
        "source_line_id"
    )

    source_text = (
        source_map.get(
            str(source_line_id)
        )
    )

    marker = claimed_id_marker(
        item.get(
            "constraint_id"
        )
    )

    if source_text is None:
        status = (
            "SOURCE_LINE_NOT_FOUND"
        )
        marker_present = None

    elif marker is None:
        status = (
            "NO_EXPLICIT_NCPR_CLAIM"
        )
        marker_present = None

    else:
        marker_present = (
            marker in source_text
        )

        status = (
            "CLAIM_SUPPORTED_BY_SOURCE_BLOCK"
            if marker_present
            else
            "CLAIM_NOT_PRESENT_IN_SOURCE_BLOCK"
        )

    return {
        "constraint_id": item.get(
            "constraint_id"
        ),
        "type": item.get(
            "type"
        ),
        "source_line_id": (
            source_line_id
        ),
        "expected_source_marker": (
            marker
        ),
        "marker_present_in_source_block": (
            marker_present
        ),
        "status": status,
    }


def type_counts(
    items: list[dict[str, Any]],
) -> dict[str, int]:
    counts = Counter(
        str(
            item.get(
                "type",
                "MISSING",
            )
        )
        for item in items
    )

    return dict(
        sorted(
            counts.items()
        )
    )


def comparison_status(
    run_02_items: list[dict[str, Any]],
    run_03_items: list[dict[str, Any]],
) -> str:
    count_02 = len(
        run_02_items
    )

    count_03 = len(
        run_03_items
    )

    if (
        count_02 > 0
        and
        count_03 == 0
    ):
        return (
            "LOST_IN_RUN_03"
        )

    if (
        count_02 == 0
        and
        count_03 > 0
    ):
        return (
            "NEW_IN_RUN_03"
        )

    if count_02 != count_03:
        return (
            "CONSTRAINT_COUNT_CHANGED"
        )

    if type_counts(
        run_02_items
    ) != type_counts(
        run_03_items
    ):
        return (
            "TYPE_DISTRIBUTION_CHANGED"
        )

    return (
        "COUNT_AND_TYPE_DISTRIBUTION_UNCHANGED"
    )


def main() -> None:
    required_files = [
        RUN_02_FILE,
        RUN_03_FILE,
        PREPROCESS_02_FILE,
        PREPROCESS_03_FILE,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found:\n"
                f"{path}"
            )

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} "
            "already exists.\n"
            "Comparison artifact will "
            "not be overwritten."
        )

    run_02 = load_json(
        RUN_02_FILE
    )

    run_03 = load_json(
        RUN_03_FILE
    )

    preprocess_02 = load_json(
        PREPROCESS_02_FILE
    )

    preprocess_03 = load_json(
        PREPROCESS_03_FILE
    )

    constraints_02 = get_constraints(
        run_02
    )

    constraints_03 = get_constraints(
        run_03
    )

    source_map_02 = get_source_map(
        preprocess_02
    )

    source_map_03 = get_source_map(
        preprocess_03
    )

    discovered_02 = set(
        normalize_constraint_id(
            item.get(
                "constraint_id"
            )
        )
        for item in constraints_02
    )

    discovered_03 = set(
        normalize_constraint_id(
            item.get(
                "constraint_id"
            )
        )
        for item in constraints_03
    )

    target_found_02 = [
        requirement_id
        for requirement_id
        in TARGET_REQUIREMENT_IDS
        if requirement_id
        in discovered_02
    ]

    target_found_03 = [
        requirement_id
        for requirement_id
        in TARGET_REQUIREMENT_IDS
        if requirement_id
        in discovered_03
    ]

    target_lost = [
        requirement_id
        for requirement_id
        in TARGET_REQUIREMENT_IDS
        if (
            requirement_id
            in discovered_02
            and
            requirement_id
            not in discovered_03
        )
    ]

    target_new = [
        requirement_id
        for requirement_id
        in TARGET_REQUIREMENT_IDS
        if (
            requirement_id
            not in discovered_02
            and
            requirement_id
            in discovered_03
        )
    ]

    per_requirement = []

    for requirement_id in (
        TARGET_REQUIREMENT_IDS
    ):
        items_02 = target_constraints(
            constraints_02,
            requirement_id,
        )

        items_03 = target_constraints(
            constraints_03,
            requirement_id,
        )

        per_requirement.append(
            {
                "requirement_id": (
                    requirement_id
                ),
                "comparison_status": (
                    comparison_status(
                        items_02,
                        items_03,
                    )
                ),
                "run_02": {
                    "constraint_count": len(
                        items_02
                    ),
                    "type_counts": (
                        type_counts(
                            items_02
                        )
                    ),
                    "constraints": [
                        compact_constraint(
                            item
                        )
                        for item
                        in items_02
                    ],
                    "attribution_checks": [
                        attribution_check(
                            item,
                            source_map_02,
                        )
                        for item
                        in items_02
                    ],
                },
                "run_03": {
                    "constraint_count": len(
                        items_03
                    ),
                    "type_counts": (
                        type_counts(
                            items_03
                        )
                    ),
                    "constraints": [
                        compact_constraint(
                            item
                        )
                        for item
                        in items_03
                    ],
                    "attribution_checks": [
                        attribution_check(
                            item,
                            source_map_03,
                        )
                        for item
                        in items_03
                    ],
                },
            }
        )

    run_02_attribution = [
        attribution_check(
            item,
            source_map_02,
        )
        for item
        in constraints_02
    ]

    run_03_attribution = [
        attribution_check(
            item,
            source_map_03,
        )
        for item
        in constraints_03
    ]

    run_02_mismatches = [
        item
        for item
        in run_02_attribution
        if item.get(
            "status"
        )
        == (
            "CLAIM_NOT_PRESENT_"
            "IN_SOURCE_BLOCK"
        )
    ]

    run_03_mismatches = [
        item
        for item
        in run_03_attribution
        if item.get(
            "status"
        )
        == (
            "CLAIM_NOT_PRESENT_"
            "IN_SOURCE_BLOCK"
        )
    ]

    artifact = {
        "metadata": {
            "stage": (
                "BLIND_RUN_02_VS_03_"
                "DETERMINISTIC_COMPARISON"
            ),
            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
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
            "run_03_file": str(
                RUN_03_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "run_03_sha256": (
                sha256_file(
                    RUN_03_FILE
                )
            ),
            "preprocess_02_file": str(
                PREPROCESS_02_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "preprocess_02_sha256": (
                sha256_file(
                    PREPROCESS_02_FILE
                )
            ),
            "preprocess_03_file": str(
                PREPROCESS_03_FILE.relative_to(
                    PROJECT_ROOT
                )
            ),
            "preprocess_03_sha256": (
                sha256_file(
                    PREPROCESS_03_FILE
                )
            ),
            "reference_file_used": False,
            "semantic_correctness_judged": (
                False
            ),
            "automatic_pass_fail": False,
            "target_ids_used_only_after_blind_runs": (
                True
            ),
        },
        "summary": {
            "target_requirement_count": len(
                TARGET_REQUIREMENT_IDS
            ),
            "run_02_total_extracted": len(
                constraints_02
            ),
            "run_03_total_extracted": len(
                constraints_03
            ),
            "run_02_target_requirements_found": len(
                target_found_02
            ),
            "run_03_target_requirements_found": len(
                target_found_03
            ),
            "run_02_target_ids": (
                target_found_02
            ),
            "run_03_target_ids": (
                target_found_03
            ),
            "target_ids_lost_in_run_03": (
                target_lost
            ),
            "target_ids_new_in_run_03": (
                target_new
            ),
            "run_02_type_counts_all": (
                type_counts(
                    constraints_02
                )
            ),
            "run_03_type_counts_all": (
                type_counts(
                    constraints_03
                )
            ),
            "run_02_source_attribution_mismatch_count": (
                len(
                    run_02_mismatches
                )
            ),
            "run_03_source_attribution_mismatch_count": (
                len(
                    run_03_mismatches
                )
            ),
        },
        "source_attribution": {
            "run_02_checks": (
                run_02_attribution
            ),
            "run_03_checks": (
                run_03_attribution
            ),
            "run_02_mismatches": (
                run_02_mismatches
            ),
            "run_03_mismatches": (
                run_03_mismatches
            ),
        },
        "per_requirement": (
            per_requirement
        ),
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
        "=== BLIND RUN #2 VS #3 ==="
    )

    print(
        "Run #2 total extracted:",
        len(
            constraints_02
        ),
    )

    print(
        "Run #3 total extracted:",
        len(
            constraints_03
        ),
    )

    print()

    print(
        "Run #2 target IDs found:",
        len(
            target_found_02
        ),
        "/",
        len(
            TARGET_REQUIREMENT_IDS
        ),
    )

    print(
        "Run #3 target IDs found:",
        len(
            target_found_03
        ),
        "/",
        len(
            TARGET_REQUIREMENT_IDS
        ),
    )

    print()

    print(
        "Lost in Run #3:",
        target_lost,
    )

    print(
        "New in Run #3:",
        target_new,
    )

    print()

    print(
        "Run #2 attribution mismatches:",
        len(
            run_02_mismatches
        ),
    )

    print(
        "Run #3 attribution mismatches:",
        len(
            run_03_mismatches
        ),
    )

    print()

    print(
        "=== PER REQUIREMENT ==="
    )

    for item in per_requirement:
        print(
            f"{item['requirement_id']}: "
            f"{item['comparison_status']} | "
            f"Run2="
            f"{item['run_02']['constraint_count']} "
            f"{item['run_02']['type_counts']} | "
            f"Run3="
            f"{item['run_03']['constraint_count']} "
            f"{item['run_03']['type_counts']}"
        )

    print()

    if run_03_mismatches:
        print(
            "=== RUN #3 ATTRIBUTION "
            "MISMATCHES ==="
        )

        for item in (
            run_03_mismatches
        ):
            print(
                f"{item['constraint_id']} | "
                f"{item['type']} | "
                f"source="
                f"{item['source_line_id']} | "
                f"{item['status']}"
            )

        print()

    print(
        f"Saved: {OUTPUT_FILE}"
    )

    print(
        "No AI call was executed."
    )

    print(
        "No frozen reference was read."
    )


if __name__ == "__main__":
    main()