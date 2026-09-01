from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]

CASE_DIR = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
)

SOURCE_PDF = (
    CASE_DIR
    / "source"
    / "NASA-SPEC-5022_Change2_Revalidated_2026.pdf"
)

REFERENCE_DIR = CASE_DIR / "reference"

RUN_A_FILE = REFERENCE_DIR / "candidate_run_a.json"
RUN_B_FILE = REFERENCE_DIR / "candidate_run_b.json"
PRECHECK_FILE = REFERENCE_DIR / "comparison_precheck.json"
ADJUDICATION_FILE = REFERENCE_DIR / "adjudication_result.json"

OUTPUT_FILE = REFERENCE_DIR / "reference_v1.json"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b"",
        ):
            hasher.update(chunk)

    return hasher.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Required file not found:\n{path}"
        )

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def require_false(
    metadata: dict[str, Any],
    field: str,
) -> None:
    if metadata.get(field) is not False:
        raise ValueError(
            f"Reference independence check failed: "
            f"{field} must be false."
        )


def main() -> None:
    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Frozen Reference v1 will not be overwritten."
        )

    run_a = load_json(RUN_A_FILE)
    run_b = load_json(RUN_B_FILE)
    precheck = load_json(PRECHECK_FILE)
    adjudication_artifact = load_json(
        ADJUDICATION_FILE
    )

    if not SOURCE_PDF.exists():
        raise FileNotFoundError(
            f"NASA source PDF not found:\n{SOURCE_PDF}"
        )

    source_sha256 = sha256_file(SOURCE_PDF)
    run_a_sha256 = sha256_file(RUN_A_FILE)
    run_b_sha256 = sha256_file(RUN_B_FILE)
    precheck_sha256 = sha256_file(PRECHECK_FILE)
    adjudication_sha256 = sha256_file(
        ADJUDICATION_FILE
    )

    metadata_a = run_a.get(
        "reference_metadata",
        {},
    )
    metadata_b = run_b.get(
        "reference_metadata",
        {},
    )
    adjudication_metadata = (
        adjudication_artifact.get(
            "adjudication_metadata",
            {},
        )
    )

    # -------------------------------------------------
    # 1. Source integrity
    # -------------------------------------------------

    if metadata_a.get(
        "source_sha256"
    ) != source_sha256:
        raise ValueError(
            "Run A source hash does not match "
            "the current NASA PDF."
        )

    if metadata_b.get(
        "source_sha256"
    ) != source_sha256:
        raise ValueError(
            "Run B source hash does not match "
            "the current NASA PDF."
        )

    if adjudication_metadata.get(
        "source_sha256"
    ) != source_sha256:
        raise ValueError(
            "Adjudication source hash does not match "
            "the current NASA PDF."
        )

    # -------------------------------------------------
    # 2. Candidate integrity
    # -------------------------------------------------

    if adjudication_metadata.get(
        "run_a_sha256"
    ) != run_a_sha256:
        raise ValueError(
            "Run A changed after adjudication."
        )

    if adjudication_metadata.get(
        "run_b_sha256"
    ) != run_b_sha256:
        raise ValueError(
            "Run B changed after adjudication."
        )

    if adjudication_metadata.get(
        "precheck_sha256"
    ) != precheck_sha256:
        raise ValueError(
            "Precheck changed after adjudication."
        )

    # -------------------------------------------------
    # 3. Independence checks
    # -------------------------------------------------

    require_false(
        metadata_a,
        "prototype_output_available_to_builder",
    )
    require_false(
        metadata_a,
        "expected_solver_result_available_to_builder",
    )

    require_false(
        metadata_b,
        "prototype_output_available_to_builder",
    )
    require_false(
        metadata_b,
        "expected_solver_result_available_to_builder",
    )

    require_false(
        adjudication_metadata,
        "prototype_output_available",
    )
    require_false(
        adjudication_metadata,
        "solver_output_available",
    )
    require_false(
        adjudication_metadata,
        "expected_result_available",
    )

    # -------------------------------------------------
    # 4. Target-set integrity
    # -------------------------------------------------

    targets_a = metadata_a.get(
        "target_requirement_ids"
    )
    targets_b = metadata_b.get(
        "target_requirement_ids"
    )

    if not isinstance(targets_a, list):
        raise ValueError(
            "Run A target_requirement_ids "
            "must be a list."
        )

    if targets_a != targets_b:
        raise ValueError(
            "Run A and Run B used different "
            "target requirement sets."
        )

    if len(targets_a) != len(set(targets_a)):
        raise ValueError(
            "Duplicate target requirement IDs found."
        )

    adjudication = adjudication_artifact.get(
        "adjudication",
        {},
    )

    requirements = adjudication.get(
        "requirements"
    )

    if not isinstance(requirements, list):
        raise ValueError(
            "Adjudication requirements must be a list."
        )

    requirement_ids = [
        item.get("requirement_id")
        for item in requirements
        if isinstance(item, dict)
    ]

    if len(requirement_ids) != len(
        requirements
    ):
        raise ValueError(
            "Malformed requirement entry found."
        )

    if len(requirement_ids) != len(
        set(requirement_ids)
    ):
        raise ValueError(
            "Duplicate adjudicated requirement IDs found."
        )

    if set(requirement_ids) != set(
        targets_a
    ):
        raise ValueError(
            "Adjudicated requirement set does not match "
            "the original target set."
        )

    # -------------------------------------------------
    # 5. Freeze eligibility
    # -------------------------------------------------

    frozen_requirements = []

    by_id = {
        item["requirement_id"]: item
        for item in requirements
    }

    for requirement_id in targets_a:
        item = by_id[requirement_id]

        if item.get("verdict") != "AGREE":
            raise ValueError(
                f"{requirement_id} cannot be frozen: "
                f"verdict={item.get('verdict')}"
            )

        if item.get(
            "needs_human_review"
        ) is not False:
            raise ValueError(
                f"{requirement_id} cannot be frozen: "
                "human review is still required."
            )

        if item.get(
            "run_a_source_supported"
        ) is not True:
            raise ValueError(
                f"{requirement_id}: "
                "Run A is not source-supported."
            )

        if item.get(
            "run_b_source_supported"
        ) is not True:
            raise ValueError(
                f"{requirement_id}: "
                "Run B is not source-supported."
            )

        source_location = item.get(
            "source_location"
        )
        meaning = item.get(
            "canonical_engineering_meaning"
        )

        if not isinstance(
            source_location,
            str,
        ) or not source_location.strip():
            raise ValueError(
                f"{requirement_id}: "
                "missing source location."
            )

        if not isinstance(
            meaning,
            str,
        ) or not meaning.strip():
            raise ValueError(
                f"{requirement_id}: "
                "missing canonical engineering meaning."
            )

        frozen_requirements.append(
            {
                "requirement_id": requirement_id,
                "source_location": source_location,
                "source_excerpt": item.get(
                    "source_excerpt"
                ),
                "engineering_meaning": meaning,
                "semantic_categories": item.get(
                    "canonical_semantic_categories",
                    [],
                ),
                "normalized_constraints": item.get(
                    "canonical_constraints",
                    [],
                ),
                "coverage_or_condition": item.get(
                    "coverage_or_condition"
                ),
                "reference_status": (
                    "FROZEN_AGREED_REFERENCE"
                ),
            }
        )

    # -------------------------------------------------
    # 6. Create frozen reference
    # -------------------------------------------------

    frozen_reference = {
        "reference_metadata": {
            "schema_version": 1,
            "reference_id": (
                "NASA-SPEC-5022-NCPR18-29-v1"
            ),
            "status": "FROZEN_REFERENCE_V1",
            "frozen_at_utc": datetime.now(
                timezone.utc
            ).isoformat(),
            "method": (
                "AI-assisted source-grounded "
                "independent reference generation"
            ),
            "source_file": str(
                SOURCE_PDF.relative_to(
                    PROJECT_ROOT
                )
            ),
            "source_sha256": source_sha256,
            "run_a_sha256": run_a_sha256,
            "run_b_sha256": run_b_sha256,
            "precheck_sha256": precheck_sha256,
            "adjudication_sha256": (
                adjudication_sha256
            ),
            "target_requirement_ids": targets_a,
            "prototype_output_exposed": False,
            "solver_output_exposed": False,
            "expected_result_exposed": False,
            "note": (
                "This reference was frozen before "
                "prototype evaluation. It is an "
                "AI-assisted source-grounded benchmark "
                "reference, not a claim of independent "
                "expert certification."
            ),
        },
        "requirements": frozen_requirements,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            frozen_reference,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=== REFERENCE FREEZE COMPLETE ===")
    print(
        f"Reference ID: "
        f"{frozen_reference['reference_metadata']['reference_id']}"
    )
    print(
        f"Requirements frozen: "
        f"{len(frozen_requirements)}"
    )
    print(
        f"Source SHA-256: {source_sha256}"
    )
    print(
        f"Run A SHA-256: {run_a_sha256}"
    )
    print(
        f"Run B SHA-256: {run_b_sha256}"
    )
    print(
        f"Adjudication SHA-256: "
        f"{adjudication_sha256}"
    )
    print()
    print(f"Saved: {OUTPUT_FILE}")
    print()
    print(
        "Prototype evaluation may begin only "
        "after this frozen reference is hashed "
        "and protected."
    )


if __name__ == "__main__":
    main()