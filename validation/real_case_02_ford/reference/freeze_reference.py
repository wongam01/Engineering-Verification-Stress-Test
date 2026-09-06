from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]

CASE_DIR = (
    PROJECT_ROOT
    / "validation"
    / "real_case_02_ford"
)

REFERENCE_DIR = CASE_DIR / "reference"

INPUT_FILE = (
    REFERENCE_DIR
    / "reference_input_v1.json"
)

OUTPUT_FILE = (
    REFERENCE_DIR
    / "reference_v1.json"
)


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

    data = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(data, dict):
        raise ValueError(
            f"Expected top-level JSON object:\n{path}"
        )

    return data


def require_exact(
    mapping: dict[str, Any],
    field: str,
    expected: Any,
) -> None:
    actual = mapping.get(field)

    if actual != expected:
        raise ValueError(
            f"Pre-freeze integrity check failed: "
            f"{field} must be {expected!r}, "
            f"got {actual!r}."
        )


def verify_sources(
    reference_input: dict[str, Any],
) -> list[dict[str, str]]:
    sources = reference_input.get("sources")

    if not isinstance(sources, list):
        raise ValueError(
            "sources must be a list."
        )

    if not sources:
        raise ValueError(
            "At least one source is required."
        )

    verified_sources: list[dict[str, str]] = []

    seen_source_ids: set[str] = set()
    seen_files: set[str] = set()

    for source in sources:
        if not isinstance(source, dict):
            raise ValueError(
                "Each source entry must be an object."
            )

        source_id = source.get("source_id")
        source_file = source.get("file")
        expected_sha256 = source.get("sha256")

        if not isinstance(source_id, str) or not source_id:
            raise ValueError(
                "Each source requires a non-empty source_id."
            )

        if source_id in seen_source_ids:
            raise ValueError(
                f"Duplicate source_id: {source_id}"
            )

        seen_source_ids.add(source_id)

        if not isinstance(source_file, str) or not source_file:
            raise ValueError(
                f"{source_id}: missing source file."
            )

        if source_file in seen_files:
            raise ValueError(
                f"Duplicate source file: {source_file}"
            )

        seen_files.add(source_file)

        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
        ):
            raise ValueError(
                f"{source_id}: invalid recorded SHA-256."
            )

        path = PROJECT_ROOT / source_file

        if not path.exists():
            raise FileNotFoundError(
                f"{source_id}: source file not found:\n"
                f"{path}"
            )

        actual_sha256 = sha256_file(path)

        if actual_sha256 != expected_sha256:
            raise ValueError(
                f"{source_id}: source SHA-256 mismatch.\n"
                f"Recorded: {expected_sha256}\n"
                f"Current:  {actual_sha256}\n"
                "Source bytes changed before freeze."
            )

        verified_sources.append(
            {
                "source_id": source_id,
                "file": source_file,
                "sha256": actual_sha256,
            }
        )

    return verified_sources


def verify_pre_freeze_state(
    reference_input: dict[str, Any],
) -> None:
    metadata = reference_input.get(
        "reference_metadata"
    )

    if not isinstance(metadata, dict):
        raise ValueError(
            "reference_metadata must be an object."
        )

    require_exact(
        metadata,
        "status",
        "PRE_FREEZE_REVIEW",
    )

    require_exact(
        metadata,
        "prototype_output_used_to_define_case",
        False,
    )

    require_exact(
        metadata,
        "solver_executed_before_reference_definition",
        False,
    )

    require_exact(
        metadata,
        "solver_output_available_during_reference_definition",
        False,
    )

    expected_result = reference_input.get(
        "expected_result"
    )

    if not isinstance(expected_result, dict):
        raise ValueError(
            "expected_result must be an object."
        )

    require_exact(
        expected_result,
        "defined_before_solver_execution",
        True,
    )

    if expected_result.get("exact_witness") is not None:
        raise ValueError(
            "exact_witness must remain null before freeze."
        )

    witness_class = expected_result.get(
        "expected_witness_class"
    )

    if not isinstance(witness_class, dict):
        raise ValueError(
            "expected_witness_class must be an object."
        )


def build_frozen_reference(
    reference_input: dict[str, Any],
    input_sha256: str,
    verified_sources: list[dict[str, str]],
) -> dict[str, Any]:
    frozen = copy.deepcopy(reference_input)

    metadata = frozen["reference_metadata"]

    metadata["status"] = "FROZEN_REFERENCE_V1"
    metadata["frozen_at_utc"] = (
        datetime.now(timezone.utc).isoformat()
    )
    metadata["reference_input_file"] = (
        "validation/real_case_02_ford/"
        "reference/reference_input_v1.json"
    )
    metadata["reference_input_sha256"] = (
        input_sha256
    )
    metadata["source_integrity_verified"] = True
    metadata["solver_executed_before_freeze"] = False

    metadata["note"] = (
        "Frozen source-grounded Ford Test #2B "
        "reference created before solver execution. "
        "The expected solver result and witness class "
        "were defined in the hashed pre-freeze input."
    )

    frozen["freeze_manifest"] = {
        "reference_input_sha256": input_sha256,
        "verified_sources": verified_sources,
        "solver_output_used_for_freeze": False,
        "prototype_output_used_for_freeze": False,
    }

    return frozen


def main() -> None:
    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Frozen Reference v1 will not be overwritten."
        )

    reference_input = load_json(INPUT_FILE)

    verify_pre_freeze_state(
        reference_input
    )

    verified_sources = verify_sources(
        reference_input
    )

    input_sha256 = sha256_file(
        INPUT_FILE
    )

    frozen = build_frozen_reference(
        reference_input=reference_input,
        input_sha256=input_sha256,
        verified_sources=verified_sources,
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            frozen,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    print("FORD TEST #2B REFERENCE FREEZE")
    print("--------------------------------")
    print("Status: FROZEN_REFERENCE_V1")
    print(
        f"Reference input SHA-256: "
        f"{input_sha256}"
    )

    for source in verified_sources:
        print(
            f"Source verified: "
            f"{source['source_id']} "
            f"{source['sha256']}"
        )

    print(f"Frozen file: {OUTPUT_FILE}")
    print(
        "Solver executed before freeze: NO"
    )


if __name__ == "__main__":
    main()
