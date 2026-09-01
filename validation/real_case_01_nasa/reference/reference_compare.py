from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]

REFERENCE_DIR = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "reference"
)

RUN_A_FILE = REFERENCE_DIR / "candidate_run_a.json"
RUN_B_FILE = REFERENCE_DIR / "candidate_run_b.json"

OUTPUT_FILE = REFERENCE_DIR / "comparison_precheck.json"


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)

    return json.loads(path.read_text(encoding="utf-8"))


def normalize_text(value: str | None) -> str | None:
    if value is None:
        return None

    value = value.casefold()
    value = value.replace("×", "x")
    value = value.replace("≥", ">=")
    value = value.replace("≤", "<=")

    value = re.sub(r"\s+", " ", value)
    value = value.strip()

    return value


def normalize_string_list(values: list[str]) -> list[str]:
    normalized = [
        normalize_text(value)
        for value in values
    ]

    return sorted(
        value
        for value in normalized
        if value is not None
    )


def requirement_map(
    artifact: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    candidate = artifact.get("candidate")

    if not isinstance(candidate, dict):
        raise ValueError("candidate must be an object")

    requirements = candidate.get("requirements")

    if not isinstance(requirements, list):
        raise ValueError("candidate.requirements must be a list")

    result: dict[str, dict[str, Any]] = {}

    for item in requirements:
        if not isinstance(item, dict):
            raise ValueError(
                "Every requirement must be an object"
            )

        requirement_id = item.get("requirement_id")

        if not isinstance(requirement_id, str):
            raise ValueError(
                "requirement_id must be a string"
            )

        if requirement_id in result:
            raise ValueError(
                f"Duplicate requirement ID: {requirement_id}"
            )

        result[requirement_id] = item

    return result


def compare_requirement(
    requirement_id: str,
    run_a: dict[str, Any],
    run_b: dict[str, Any],
) -> dict[str, Any]:
    hard_conflicts: list[str] = []
    semantic_review_fields: list[str] = []
    exact_agree_fields: list[str] = []

    # Fields where disagreement is a direct contradiction.
    hard_fields = [
        "found",
        "evidence_status",
    ]

    for field in hard_fields:
        if run_a.get(field) == run_b.get(field):
            exact_agree_fields.append(field)
        else:
            hard_conflicts.append(field)

    # Human-review flags are important but can differ because
    # confidence/review judgment is model-generated.
    if (
        run_a.get("needs_human_review")
        == run_b.get("needs_human_review")
    ):
        exact_agree_fields.append(
            "needs_human_review"
        )
    else:
        semantic_review_fields.append(
            "needs_human_review"
        )

    # Categories are compared as sets because ordering is irrelevant.
    categories_a = sorted(
        run_a.get("semantic_categories", [])
    )
    categories_b = sorted(
        run_b.get("semantic_categories", [])
    )

    if categories_a == categories_b:
        exact_agree_fields.append(
            "semantic_categories"
        )
    else:
        semantic_review_fields.append(
            "semantic_categories"
        )

    # Source location may use slightly different wording/page notation.
    source_a = normalize_text(
        run_a.get("source_location")
    )
    source_b = normalize_text(
        run_b.get("source_location")
    )

    if source_a == source_b:
        exact_agree_fields.append(
            "source_location"
        )
    else:
        semantic_review_fields.append(
            "source_location"
        )

    # Constraint strings can express the same semantics differently.
    constraints_a = normalize_string_list(
        run_a.get("normalized_constraints", [])
    )
    constraints_b = normalize_string_list(
        run_b.get("normalized_constraints", [])
    )

    if constraints_a == constraints_b:
        exact_agree_fields.append(
            "normalized_constraints"
        )
    else:
        semantic_review_fields.append(
            "normalized_constraints"
        )

    # Meaning/excerpts are intentionally NOT treated as exact-answer
    # fields. Differences here require semantic review only.
    meaning_a = normalize_text(
        run_a.get("engineering_meaning")
    )
    meaning_b = normalize_text(
        run_b.get("engineering_meaning")
    )

    if meaning_a == meaning_b:
        exact_agree_fields.append(
            "engineering_meaning"
        )
    else:
        semantic_review_fields.append(
            "engineering_meaning"
        )

    excerpt_a = normalize_text(
        run_a.get("source_excerpt")
    )
    excerpt_b = normalize_text(
        run_b.get("source_excerpt")
    )

    if excerpt_a == excerpt_b:
        exact_agree_fields.append(
            "source_excerpt"
        )
    else:
        semantic_review_fields.append(
            "source_excerpt"
        )

    confidence_a = run_a.get("confidence")
    confidence_b = run_b.get("confidence")

    if confidence_a == confidence_b:
        exact_agree_fields.append(
            "confidence"
        )
    else:
        semantic_review_fields.append(
            "confidence"
        )

    if hard_conflicts:
        status = "HARD_CONFLICT"
    elif semantic_review_fields:
        status = "SEMANTIC_REVIEW_REQUIRED"
    else:
        status = "EXACT_AGREE"

    return {
        "requirement_id": requirement_id,
        "status": status,
        "hard_conflict_fields": hard_conflicts,
        "semantic_review_fields": semantic_review_fields,
        "exact_agree_fields": exact_agree_fields,
        "run_a": {
            "found": run_a.get("found"),
            "source_location": run_a.get(
                "source_location"
            ),
            "engineering_meaning": run_a.get(
                "engineering_meaning"
            ),
            "semantic_categories": run_a.get(
                "semantic_categories",
                [],
            ),
            "normalized_constraints": run_a.get(
                "normalized_constraints",
                [],
            ),
            "evidence_status": run_a.get(
                "evidence_status"
            ),
            "confidence": run_a.get("confidence"),
            "needs_human_review": run_a.get(
                "needs_human_review"
            ),
        },
        "run_b": {
            "found": run_b.get("found"),
            "source_location": run_b.get(
                "source_location"
            ),
            "engineering_meaning": run_b.get(
                "engineering_meaning"
            ),
            "semantic_categories": run_b.get(
                "semantic_categories",
                [],
            ),
            "normalized_constraints": run_b.get(
                "normalized_constraints",
                [],
            ),
            "evidence_status": run_b.get(
                "evidence_status"
            ),
            "confidence": run_b.get("confidence"),
            "needs_human_review": run_b.get(
                "needs_human_review"
            ),
        },
    }


def main() -> None:
    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists. "
            "Precheck output will not be overwritten."
        )

    run_a_artifact = load_json(RUN_A_FILE)
    run_b_artifact = load_json(RUN_B_FILE)

    metadata_a = run_a_artifact.get(
        "reference_metadata",
        {},
    )
    metadata_b = run_b_artifact.get(
        "reference_metadata",
        {},
    )

    source_hash_a = metadata_a.get(
        "source_sha256"
    )
    source_hash_b = metadata_b.get(
        "source_sha256"
    )

    if source_hash_a != source_hash_b:
        raise ValueError(
            "Run A and Run B used different source PDFs."
        )

    if (
        metadata_a.get(
            "prototype_output_available_to_builder"
        )
        is not False
        or metadata_b.get(
            "prototype_output_available_to_builder"
        )
        is not False
    ):
        raise ValueError(
            "Reference builder metadata indicates "
            "possible prototype-output exposure."
        )

    if (
        metadata_a.get(
            "expected_solver_result_available_to_builder"
        )
        is not False
        or metadata_b.get(
            "expected_solver_result_available_to_builder"
        )
        is not False
    ):
        raise ValueError(
            "Reference builder metadata indicates "
            "possible expected-result exposure."
        )

    requirements_a = requirement_map(
        run_a_artifact
    )
    requirements_b = requirement_map(
        run_b_artifact
    )

    ids_a = set(requirements_a)
    ids_b = set(requirements_b)

    if ids_a != ids_b:
        raise ValueError(
            "Run A and Run B returned different "
            "requirement ID sets."
        )

    comparisons = []

    for requirement_id in sorted(
        ids_a,
        key=lambda value: int(
            value.split()[-1]
        ),
    ):
        comparisons.append(
            compare_requirement(
                requirement_id,
                requirements_a[requirement_id],
                requirements_b[requirement_id],
            )
        )

    exact_count = sum(
        item["status"] == "EXACT_AGREE"
        for item in comparisons
    )

    semantic_review_count = sum(
        item["status"]
        == "SEMANTIC_REVIEW_REQUIRED"
        for item in comparisons
    )

    hard_conflict_count = sum(
        item["status"] == "HARD_CONFLICT"
        for item in comparisons
    )

    artifact = {
        "comparison_metadata": {
            "run_a_file": str(
                RUN_A_FILE.relative_to(PROJECT_ROOT)
            ),
            "run_b_file": str(
                RUN_B_FILE.relative_to(PROJECT_ROOT)
            ),
            "run_a_sha256": sha256_file(
                RUN_A_FILE
            ),
            "run_b_sha256": sha256_file(
                RUN_B_FILE
            ),
            "source_sha256": source_hash_a,
            "same_source_document": True,
            "prototype_output_exposed": False,
            "expected_solver_result_exposed": False,
            "comparison_method": (
                "deterministic structural precheck"
            ),
        },
        "summary": {
            "total_requirements": len(
                comparisons
            ),
            "exact_agree": exact_count,
            "semantic_review_required": (
                semantic_review_count
            ),
            "hard_conflict": hard_conflict_count,
        },
        "requirements": comparisons,
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            artifact,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print("=== REFERENCE A/B PRECHECK ===")
    print(
        f"Total: {len(comparisons)}"
    )
    print(
        f"Exact agree: {exact_count}"
    )
    print(
        "Semantic review required: "
        f"{semantic_review_count}"
    )
    print(
        f"Hard conflict: {hard_conflict_count}"
    )
    print()

    for item in comparisons:
        print(
            f"{item['requirement_id']}: "
            f"{item['status']}"
        )

        if item["hard_conflict_fields"]:
            print(
                "  Hard conflicts:",
                ", ".join(
                    item[
                        "hard_conflict_fields"
                    ]
                ),
            )

        if item["semantic_review_fields"]:
            print(
                "  Semantic review:",
                ", ".join(
                    item[
                        "semantic_review_fields"
                    ]
                ),
            )

    print()
    print(
        f"Saved: {OUTPUT_FILE}"
    )
    print()
    print(
        "NOTE: SEMANTIC_REVIEW_REQUIRED does "
        "not mean the two runs disagree in meaning."
    )
    print(
        "It means deterministic string/field "
        "comparison is insufficient."
    )


if __name__ == "__main__":
    main()