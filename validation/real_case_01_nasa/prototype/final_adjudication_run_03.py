from __future__ import annotations

import hashlib
import json

from collections import Counter
from datetime import (
    datetime,
    timezone,
)
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

REFERENCE_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "reference"
    / "reference_v1.json"
)

RUN_03_FILE = (
    PROTOTYPE_DIR
    / "blind_ai_extract_run_03.json"
)

COMPARISON_FILE = (
    PROTOTYPE_DIR
    / "blind_run_02_vs_03_comparison.json"
)

REFERENCE_SNAPSHOT_FILE = (
    PROTOTYPE_DIR
    / "run_03_vs_frozen_reference_snapshot.json"
)

CORE_ACCEPTABILITY_FILE = (
    PROTOTYPE_DIR
    / "run_03_ai_to_core_acceptability.json"
)

PREPROCESS_FILE = (
    PROTOTYPE_DIR
    / "blind_preprocess_run_04.json"
)

OUTPUT_FILE = (
    PROTOTYPE_DIR
    / "final_adjudication_run_03.json"
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


def relative_path(
    path: Path,
) -> str:
    return str(
        path.relative_to(
            PROJECT_ROOT
        )
    )


def evidence_record(
    path: Path,
) -> dict[str, str]:
    return {
        "file": relative_path(
            path
        ),
        "sha256": sha256_file(
            path
        ),
    }


def main() -> None:
    evidence_files = {
        "frozen_reference": (
            REFERENCE_FILE
        ),
        "blind_run_03": (
            RUN_03_FILE
        ),
        "run_02_vs_03_comparison": (
            COMPARISON_FILE
        ),
        "run_03_reference_snapshot": (
            REFERENCE_SNAPSHOT_FILE
        ),
        "run_03_core_acceptability": (
            CORE_ACCEPTABILITY_FILE
        ),
        "preprocess_run_04": (
            PREPROCESS_FILE
        ),
    }

    for name, path in (
        evidence_files.items()
    ):
        if not path.exists():
            raise FileNotFoundError(
                f"Missing evidence "
                f"{name}:\n{path}"
            )

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} "
            "already exists.\n"
            "Final adjudication will "
            "not be overwritten."
        )

    judgments = [
        {
            "requirement_id": "NCPR 18",
            "status": (
                "SAFE_UNSUPPORTED"
            ),
            "reason": (
                "Requirement was discovered "
                "from its explicit source block. "
                "The 1.5xMEOP multiplier "
                "relationship was not reduced "
                "to a false scalar lower bound; "
                "it was blocked for review."
            ),
        },
        {
            "requirement_id": "NCPR 19",
            "status": (
                "ATTRIBUTION_FAILURE_"
                "UNSAFE_CORE_ACCEPTANCE"
            ),
            "reason": (
                "Run #3 outputs labeled NCPR 19 "
                "came from anonymous source block "
                "L9 rather than the explicit "
                "NCPR 19 source block. "
                "One resulting upper_bound was "
                "Core-accepted, so raw Core "
                "acceptance must not be treated "
                "as semantic correctness."
            ),
        },
        {
            "requirement_id": "NCPR 20",
            "status": (
                "DISCOVERY_MISS"
            ),
            "reason": (
                "No Run #3 constraint was "
                "produced for this target "
                "requirement."
            ),
        },
        {
            "requirement_id": "NCPR 21",
            "status": (
                "DISCOVERY_MISS"
            ),
            "reason": (
                "No Run #3 constraint was "
                "produced for this target "
                "requirement."
            ),
        },
        {
            "requirement_id": "NCPR 22",
            "status": (
                "DISCOVERY_MISS"
            ),
            "reason": (
                "No Run #3 constraint was "
                "produced for this target "
                "requirement."
            ),
        },
        {
            "requirement_id": "NCPR 23",
            "status": (
                "DISCOVERY_MISS"
            ),
            "reason": (
                "No Run #3 constraint was "
                "produced for this target "
                "requirement."
            ),
        },
        {
            "requirement_id": "NCPR 24",
            "status": (
                "DISCOVERY_MISS"
            ),
            "reason": (
                "The external-analysis "
                "requirement was not discovered "
                "in Run #3."
            ),
        },
        {
            "requirement_id": "NCPR 25",
            "status": (
                "SAFE_UNSUPPORTED"
            ),
            "reason": (
                "The four-times-design-life "
                "relationship was discovered "
                "but conservatively blocked "
                "instead of being reduced to "
                "an unsupported scalar meaning."
            ),
        },
        {
            "requirement_id": "NCPR 26",
            "status": (
                "SAFE_UNSUPPORTED"
            ),
            "reason": (
                "The requirement was discovered "
                "with cross-page source "
                "continuation preserved. "
                "Its conditional, coverage, "
                "and multiplier semantics were "
                "conservatively blocked."
            ),
        },
        {
            "requirement_id": "NCPR 27",
            "status": (
                "CORRECT_CORE_READY"
            ),
            "reason": (
                "The minimum hold time of "
                "5 min was represented as a "
                "lower_bound without review "
                "and accepted by the Core."
            ),
        },
        {
            "requirement_id": "NCPR 28",
            "status": (
                "SAFE_UNSUPPORTED"
            ),
            "reason": (
                "The diameter-dependent "
                "2.5xMEOP / 4.0xMEOP branches "
                "were no longer emitted as "
                "false executable scalar bounds. "
                "The conditional multiplier "
                "semantics were blocked "
                "for review."
            ),
        },
        {
            "requirement_id": "NCPR 29",
            "status": (
                "DISCOVERY_MISS"
            ),
            "reason": (
                "The per-lot sampling "
                "requirement was not discovered "
                "in Run #3."
            ),
        },
    ]

    status_counts = Counter(
        item["status"]
        for item in judgments
    )

    artifact = {
        "metadata": {
            "stage": (
                "NASA_TEST_01_"
                "FINAL_ADJUDICATION_RUN_03"
            ),
            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),
            "evaluator_judgments_explicit": (
                True
            ),
            "automatic_semantic_pass_fail": (
                False
            ),
            "prototype_modified_during_"
            "adjudication": False,
            "ai_api_call_during_"
            "adjudication": False,
            "solver_execution_during_"
            "adjudication": False,
            "blind_run_03_output_modified": (
                False
            ),
            "legacy_display_label_note": (
                "The Run #3 reference-alignment "
                "and AI-to-Core evaluation "
                "scripts retained a legacy "
                "'RUN #2' console banner in "
                "some print statements. "
                "Their Run #3 input/output "
                "filenames were used. "
                "Frozen evidence artifacts "
                "were not rewritten to hide "
                "this labeling issue."
            ),
        },
        "evidence": {
            name: evidence_record(
                path
            )
            for name, path
            in evidence_files.items()
        },
        "summary": {
            "target_requirement_count": 12,
            "run_02_claimed_target_ids_found": (
                12
            ),
            "run_03_claimed_target_ids_found": (
                6
            ),
            "run_03_source_grounded_target_"
            "requirements": 5,
            "run_03_lost_target_ids": [
                "NCPR 20",
                "NCPR 21",
                "NCPR 22",
                "NCPR 23",
                "NCPR 24",
                "NCPR 29",
            ],
            "raw_core_accepted_count": 2,
            "semantically_correct_core_ready_"
            "count": 1,
            "semantically_correct_core_ready_"
            "ids": [
                "NCPR 27"
            ],
            "source_attribution_mismatch_"
            "count": 2,
            "status_counts": dict(
                sorted(
                    status_counts.items()
                )
            ),
            "general_fix_cycle_02": {
                "A_multiplier_numeric_contract": (
                    "IMPROVED_FAIL_SAFE"
                ),
                "B_scientific_notation": (
                    "STRUCTURAL_NORMALIZATION_"
                    "IMPROVED_BUT_SEMANTIC_"
                    "SAFETY_INCOMPLETE"
                ),
                "C_preprocessing_attribution": (
                    "IMPROVED"
                ),
                "C_ai_level_attribution": (
                    "LIMITATION_REMAINS"
                ),
                "document_level_discovery": (
                    "REGRESSED"
                ),
            },
            "overall_conclusion": (
                "PARTIAL_SUCCESS_WITH_"
                "FAIL_SAFE_IMPROVEMENTS_AND_"
                "DOCUMENT_LEVEL_DISCOVERY_"
                "REGRESSION"
            ),
            "test_01_closure_decision": (
                "CLOSE_TEST_01_NO_RUN_04"
            ),
            "next_validation_stage": (
                "REAL_CASE_TEST_02_"
                "FULL_R_V_F_ESCAPE_SEARCH"
            ),
        },
        "requirements": judgments,
        "evaluator_note": (
            "The purpose of these labels is "
            "post-run adjudication of already "
            "frozen evidence. They are not "
            "prototype outputs, expected "
            "solver answers, or parser tuning "
            "targets, and they are not fed "
            "back into the prototype."
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
        "=== NASA TEST #1 FINAL "
        "ADJUDICATION — RUN #3 ==="
    )

    print(
        "Target requirements:",
        len(
            judgments
        ),
    )

    print()

    for (
        status,
        count,
    ) in sorted(
        status_counts.items()
    ):
        print(
            f"{status}: {count}"
        )

    print()

    print(
        "Overall:"
    )
    print(
        artifact[
            "summary"
        ][
            "overall_conclusion"
        ]
    )

    print()

    print(
        "Closure:"
    )
    print(
        artifact[
            "summary"
        ][
            "test_01_closure_decision"
        ]
    )

    print()

    print(
        "Next:"
    )
    print(
        artifact[
            "summary"
        ][
            "next_validation_stage"
        ]
    )

    print()

    print(
        f"Saved: {OUTPUT_FILE}"
    )

    print(
        "No AI call was made."
    )

    print(
        "No Solver execution was performed."
    )


if __name__ == "__main__":
    main()