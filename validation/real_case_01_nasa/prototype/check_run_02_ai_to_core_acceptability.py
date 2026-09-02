from __future__ import annotations

import hashlib
import json

from decimal import Decimal

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from src.ai.core_adapter import (
    convert_ai_constraint,
    validate_ai_extraction_structure,
)


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

RUN_02_FILE = (
    PROTOTYPE_DIR
    / "blind_ai_extract_run_02.json"
)

OUTPUT_FILE = (
    PROTOTYPE_DIR
    / "run_02_ai_to_core_acceptability.json"
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


def make_json_safe(
    value,
):
    """
    Evaluation artifact용 JSON-safe 변환.

    Core의 Decimal 값은 정밀도를 잃지 않도록
    float가 아니라 문자열로 기록한다.
    """

    if isinstance(
        value,
        Decimal,
    ):
        return str(value)

    if isinstance(
        value,
        dict,
    ):
        return {
            key: make_json_safe(item)
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            make_json_safe(item)
            for item in value
        ]

    return value


def serialize_core_constraint(
    constraint,
):
    if constraint is None:
        return None

    return make_json_safe(
        constraint.to_dict()
    )


def main() -> None:
    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Acceptability artifact will not "
            "be overwritten."
        )

    run2 = load_json(
        RUN_02_FILE
    )

    target_constraints = [
        item
        for item in run2.get(
            "constraints",
            [],
        )
        if item.get(
            "constraint_id"
        )
        in TARGET_IDS
    ]

    found_ids = {
        item.get(
            "constraint_id"
        )
        for item in target_constraints
    }

    missing_ids = [
        requirement_id
        for requirement_id in TARGET_IDS
        if requirement_id not in found_ids
    ]

    evaluations = []

    for index, extraction in enumerate(
        target_constraints,
        start=1,
    ):
        structure_valid, structure_message = (
            validate_ai_extraction_structure(
                extraction
            )
        )

        adapter_result = (
            convert_ai_constraint(
                extraction
            )
        )

        evaluations.append(
            {
                "index": index,

                "constraint_id":
                    extraction.get(
                        "constraint_id"
                    ),

                "source_line_id":
                    extraction.get(
                        "source_line_id"
                    ),

                "declared_type":
                    extraction.get(
                        "type"
                    ),

                "needs_review":
                    extraction.get(
                        "needs_review"
                    ),

                "review_reason":
                    extraction.get(
                        "review_reason"
                    ),

                "input_fields": {
                    "unit":
                        extraction.get(
                            "unit"
                        ),

                    "variable":
                        extraction.get(
                            "variable"
                        ),

                    "min":
                        extraction.get(
                            "min"
                        ),

                    "max":
                        extraction.get(
                            "max"
                        ),

                    "left":
                        extraction.get(
                            "left"
                        ),

                    "right":
                        extraction.get(
                            "right"
                        ),

                    "variables":
                        extraction.get(
                            "variables"
                        ),

                    "limit":
                        extraction.get(
                            "limit"
                        ),
                },

                "structure_guard": {
                    "valid":
                        structure_valid,

                    "message":
                        structure_message,
                },

                "core_adapter": {
                    "accepted":
                        adapter_result.accepted,

                    "message":
                        adapter_result.message,

                    "core_constraint":
                        serialize_core_constraint(
                            adapter_result.constraint
                        ),
                },
            }
        )

    accepted_count = sum(
        1
        for item in evaluations
        if item[
            "core_adapter"
        ][
            "accepted"
        ]
    )

    rejected_count = (
        len(evaluations)
        - accepted_count
    )

    structure_valid_count = sum(
        1
        for item in evaluations
        if item[
            "structure_guard"
        ][
            "valid"
        ]
    )

    structure_invalid_count = (
        len(evaluations)
        - structure_valid_count
    )

    accepted_by_id = Counter(
        item["constraint_id"]
        for item in evaluations
        if item[
            "core_adapter"
        ][
            "accepted"
        ]
    )

    artifact = {
        "metadata": {
            "stage": (
                "RUN_02_DETERMINISTIC_"
                "AI_TO_CORE_ACCEPTABILITY"
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

            "run_02_sha256":
                sha256_file(
                    RUN_02_FILE
                ),

            "target_ids":
                list(
                    TARGET_IDS
                ),

            "ai_api_called":
                False,

            "frozen_reference_used":
                False,

            "solver_executed":
                False,

            "check_scope": (
                "Deterministic AI extraction "
                "structure and AI-to-Core "
                "adapter acceptability only."
            ),
        },

        "summary": {
            "target_requirement_count":
                len(TARGET_IDS),

            "found_requirement_count":
                len(found_ids),

            "missing_requirement_ids":
                missing_ids,

            "target_constraint_count":
                len(evaluations),

            "structure_valid_count":
                structure_valid_count,

            "structure_invalid_count":
                structure_invalid_count,

            "core_accepted_count":
                accepted_count,

            "core_rejected_count":
                rejected_count,

            "accepted_constraints_by_id":
                dict(
                    sorted(
                        accepted_by_id.items()
                    )
                ),
        },

        "evaluations":
            evaluations,
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
        "=== RUN #2 DETERMINISTIC "
        "AI -> CORE ACCEPTABILITY ==="
    )
    print()

    print(
        "Target requirements: "
        f"{len(TARGET_IDS)}"
    )

    print(
        "Found requirements: "
        f"{len(found_ids)}"
    )

    print(
        "Target constraints: "
        f"{len(evaluations)}"
    )

    print(
        "Structure valid: "
        f"{structure_valid_count}"
    )

    print(
        "Structure invalid: "
        f"{structure_invalid_count}"
    )

    print(
        "Core accepted: "
        f"{accepted_count}"
    )

    print(
        "Core rejected: "
        f"{rejected_count}"
    )

    print()
    print(
        "=== CONSTRAINT RESULTS ==="
    )
    print()

    for item in evaluations:
        structure = item[
            "structure_guard"
        ]

        adapter = item[
            "core_adapter"
        ]

        print(
            f"{item['index']:02d}. "
            f"{item['constraint_id']} | "
            f"{item['declared_type']} | "
            f"review={item['needs_review']} | "
            f"structure="
            f"{'PASS' if structure['valid'] else 'FAIL'} | "
            f"core="
            f"{'ACCEPT' if adapter['accepted'] else 'REJECT'}"
        )

        if not structure[
            "valid"
        ]:
            print(
                "    structure reason: "
                f"{structure['message']}"
            )

        if not adapter[
            "accepted"
        ]:
            print(
                "    adapter reason: "
                f"{adapter['message']}"
            )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print()

    print(
        "No AI API call was made."
    )

    print(
        "No Frozen Reference was used."
    )

    print(
        "No Solver execution was performed."
    )


if __name__ == "__main__":
    main()