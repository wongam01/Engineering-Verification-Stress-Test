from __future__ import annotations

import hashlib
import json

from collections import Counter
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

SNAPSHOT_FILE = (
    PROTOTYPE_DIR
    / "run_02_vs_frozen_reference_snapshot.json"
)

ACCEPTABILITY_FILE = (
    PROTOTYPE_DIR
    / "run_02_ai_to_core_acceptability.json"
)

OUTPUT_FILE = (
    PROTOTYPE_DIR
    / "final_adjudication_run_02.json"
)

TARGET_IDS = tuple(
    f"NCPR {number}"
    for number in range(18, 30)
)


# =========================================================
# EVALUATOR JUDGMENTS
#
# 이 값들은 Prototype 출력이 아니다.
# Frozen Reference + Run #2 + deterministic
# AI-to-Core 결과를 바탕으로 한 명시적 평가 라벨이다.
# =========================================================

JUDGMENTS = {
    "NCPR 18": {
        "overall": "PARTIAL",
        "semantic_extraction": "PARTIAL_SUCCESS",
        "core_readiness": "REJECTED",
        "fail_safe": "PASS",
        "reason": (
            "Minimum proof-pressure meaning and lower-bound "
            "type were identified, but numeric and unit "
            "semantics were not canonically separated: "
            "min contained '1.5xMEOP'."
        ),
    },

    "NCPR 19": {
        "overall": "ATTRIBUTION_ISSUE",
        "semantic_extraction": "MISATTRIBUTED",
        "core_readiness": "REJECTED",
        "fail_safe": "PARTIAL",
        "reason": (
            "Prototype extracted numeric helium-leak "
            "constraints from an unnumbered normative "
            "paragraph attached to the NCPR 19 block rather "
            "than representing the numbered NCPR 19 "
            "coverage/procedural requirement."
        ),
    },

    "NCPR 20": {
        "overall": "SAFE_UNSUPPORTED",
        "semantic_extraction": "SCOPE_RECOGNIZED",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "Coverage/procedural requirement is outside the "
            "currently supported mathematical constraint "
            "types and was routed to review."
        ),
    },

    "NCPR 21": {
        "overall": "SAFE_UNSUPPORTED",
        "semantic_extraction": "SCOPE_RECOGNIZED",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "Coverage plus logical-OR procedural semantics "
            "were not forced into an unsupported numeric "
            "constraint."
        ),
    },

    "NCPR 22": {
        "overall": "SAFE_UNSUPPORTED",
        "semantic_extraction": "SCOPE_RECOGNIZED",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "Alternative NDT/process-control requirement "
            "was safely routed to review."
        ),
    },

    "NCPR 23": {
        "overall": "SAFE_UNSUPPORTED",
        "semantic_extraction": "SCOPE_RECOGNIZED",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "Conditional approval/governance requirement "
            "was not approximated as a supported numeric "
            "constraint."
        ),
    },

    "NCPR 24": {
        "overall": "SAFE_UNSUPPORTED_EXTERNAL_ANALYSIS",
        "semantic_extraction": "SCOPE_RECOGNIZED",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "Fracture-mechanics/crack-growth requirement "
            "requires external analysis and was safely "
            "kept outside the deterministic constraint "
            "scope."
        ),
    },

    "NCPR 25": {
        "overall": "SAFE_UNSUPPORTED_SCHEMA_GAP",
        "semantic_extraction": "PARTIAL_SUCCESS",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "The four-times operational-life relationship "
            "contains a numeric multiplier, but that "
            "relationship is not represented by the current "
            "constraint schema."
        ),
    },

    "NCPR 26": {
        "overall": "SAFE_UNSUPPORTED_COMPLEX_CONDITIONAL",
        "semantic_extraction": "PARTIAL_SUCCESS",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "Requirement combines conditional applicability, "
            "location-specific proof testing, coverage, and "
            "no-deformation/no-leakage semantics. Prototype "
            "safely routed the compound requirement to review."
        ),
    },

    "NCPR 27": {
        "overall": "CORRECT_CORE_READY",
        "semantic_extraction": "CORRECT",
        "core_readiness": "ACCEPTED",
        "fail_safe": "NOT_NEEDED",
        "reason": (
            "Hold-time lower bound was extracted as "
            "lower_bound with min=5 and unit=min and was "
            "accepted by the deterministic AI-to-Core "
            "adapter."
        ),
    },

    "NCPR 28": {
        "overall": "PARTIAL_REVIEW_REQUIRED",
        "semantic_extraction": "PARTIAL_SUCCESS",
        "core_readiness": "REJECTED",
        "fail_safe": "PASS",
        "reason": (
            "Both 2.5xMEOP and 4.0xMEOP branches were "
            "identified as lower bounds, but conditional "
            "branch semantics are not structurally supported "
            "and multiplier values were not canonically "
            "separated from units."
        ),
    },

    "NCPR 29": {
        "overall": "CLASSIFICATION_MISS_SAFE_REJECT",
        "semantic_extraction": "MISSED_SUPPORTED_NUMERIC_PATTERN",
        "core_readiness": "REJECTED_BY_DESIGN",
        "fail_safe": "PASS",
        "reason": (
            "Reference contains an explicit per-lot count "
            "threshold >= 1, but Prototype classified the "
            "sampling requirement as unsupported. The miss "
            "was safely routed to review rather than forced "
            "into the Core."
        ),
    },
}


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
            f"Required evidence not found:\n{path}"
        )

    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def main() -> None:
    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Final adjudication will not be overwritten."
        )

    if set(JUDGMENTS) != set(TARGET_IDS):
        raise RuntimeError(
            "Judgment target IDs do not match "
            "the frozen benchmark target set."
        )

    snapshot = load_json(
        SNAPSHOT_FILE
    )

    acceptability = load_json(
        ACCEPTABILITY_FILE
    )

    snapshot_by_id = {
        item["requirement_id"]: item
        for item in snapshot[
            "alignments"
        ]
    }

    acceptance_by_id = {
        requirement_id: []
        for requirement_id
        in TARGET_IDS
    }

    for evaluation in acceptability[
        "evaluations"
    ]:
        requirement_id = evaluation[
            "constraint_id"
        ]

        if requirement_id in (
            acceptance_by_id
        ):
            acceptance_by_id[
                requirement_id
            ].append(
                evaluation
            )

    adjudications = []

    for requirement_id in TARGET_IDS:
        alignment = snapshot_by_id[
            requirement_id
        ]

        deterministic = (
            acceptance_by_id[
                requirement_id
            ]
        )

        accepted_count = sum(
            1
            for item in deterministic
            if item[
                "core_adapter"
            ][
                "accepted"
            ]
        )

        adjudications.append(
            {
                "requirement_id":
                    requirement_id,

                "evidence": {
                    "reference_categories":
                        alignment[
                            "frozen_reference"
                        ][
                            "semantic_categories"
                        ],

                    "reference_normalized_constraints":
                        alignment[
                            "frozen_reference"
                        ][
                            "normalized_constraints"
                        ],

                    "prototype_types":
                        alignment[
                            "prototype_run_02"
                        ][
                            "types"
                        ],

                    "prototype_needs_review":
                        alignment[
                            "prototype_run_02"
                        ][
                            "needs_review"
                        ],

                    "deterministic_constraint_count":
                        len(
                            deterministic
                        ),

                    "core_accepted_count":
                        accepted_count,

                    "core_rejected_count":
                        (
                            len(
                                deterministic
                            )
                            - accepted_count
                        ),
                },

                "judgment":
                    JUDGMENTS[
                        requirement_id
                    ],
            }
        )

    overall_counts = Counter(
        item[
            "judgment"
        ][
            "overall"
        ]
        for item in adjudications
    )

    artifact = {
        "metadata": {
            "stage": (
                "NASA_REAL_DOCUMENT_BENCHMARK_"
                "RUN_02_FINAL_ADJUDICATION"
            ),

            "created_at_utc": (
                datetime.now(
                    timezone.utc
                ).isoformat()
            ),

            "target_ids":
                list(
                    TARGET_IDS
                ),

            "frozen_reference_alignment_file":
                str(
                    SNAPSHOT_FILE.relative_to(
                        PROJECT_ROOT
                    )
                ),

            "frozen_reference_alignment_sha256":
                sha256_file(
                    SNAPSHOT_FILE
                ),

            "deterministic_acceptability_file":
                str(
                    ACCEPTABILITY_FILE.relative_to(
                        PROJECT_ROOT
                    )
                ),

            "deterministic_acceptability_sha256":
                sha256_file(
                    ACCEPTABILITY_FILE
                ),

            "automatic_semantic_pass_fail_used":
                False,

            "judgments_are_evaluator_labels":
                True,

            "prototype_output_modified":
                False,

            "ai_api_called_for_adjudication":
                False,

            "solver_executed_for_adjudication":
                False,
        },

        "summary": {
            "target_requirement_count":
                len(
                    TARGET_IDS
                ),

            "overall_status_counts":
                dict(
                    sorted(
                        overall_counts.items()
                    )
                ),

            "benchmark_conclusion": (
                "PARTIAL_SUCCESS_WITH_IDENTIFIED_"
                "GENERALIZATION_AND_SCHEMA_LIMITATIONS"
            ),

            "interpretation": (
                "Run #2 demonstrated improved recognition "
                "of one-sided bounds and safe rejection of "
                "unsupported semantics, but also exposed "
                "numeric/unit canonicalization, source "
                "attribution, conditional representation, "
                "and sampling-classification limitations."
            ),
        },

        "adjudications":
            adjudications,
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
        "=== NASA RUN #2 FINAL ADJUDICATION ==="
    )
    print()

    for item in adjudications:
        judgment = item[
            "judgment"
        ]

        print(
            f"{item['requirement_id']}: "
            f"{judgment['overall']}"
        )

    print()
    print(
        "Overall counts:"
    )

    for status, count in sorted(
        overall_counts.items()
    ):
        print(
            f"  {status}: {count}"
        )

    print()
    print(
        "Benchmark conclusion:"
    )
    print(
        artifact[
            "summary"
        ][
            "benchmark_conclusion"
        ]
    )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()