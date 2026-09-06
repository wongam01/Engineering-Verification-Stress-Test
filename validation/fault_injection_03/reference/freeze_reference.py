import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


CASE_DIR = Path("validation/fault_injection_03")
REFERENCE_DIR = CASE_DIR / "reference"

INPUT_PATH = REFERENCE_DIR / "reference_input_v1.json"
OUTPUT_PATH = REFERENCE_DIR / "reference_v1.json"


def sha256(path: Path) -> str:
    return hashlib.sha256(
        path.read_bytes()
    ).hexdigest()


if OUTPUT_PATH.exists():
    raise FileExistsError(
        f"Refusing to overwrite frozen reference: {OUTPUT_PATH}"
    )

data = json.loads(
    INPUT_PATH.read_text(encoding="utf-8")
)

metadata = data["reference_metadata"]

if metadata["status"] != "PRE_FREEZE_REVIEW":
    raise RuntimeError(
        "Reference input is not in PRE_FREEZE_REVIEW state."
    )

if (
    metadata[
        "defined_before_official_fault_injection_run"
    ]
    is not True
):
    raise RuntimeError(
        "Expected matrix must be defined before official run."
    )

if (
    metadata[
        "official_fault_injection_output_available_during_definition"
    ]
    is not False
):
    raise RuntimeError(
        "Official run output must not be available during definition."
    )

expected_ids = {
    "T3-01",
    "T3-02",
    "T3-03",
    "T3-04",
    "T3-05",
    "T3-06",
    "T3-07",
    "T3-08",
}

actual_ids = {
    item["id"]
    for item in data["test_matrix"]
}

if actual_ids != expected_ids:
    raise RuntimeError(
        f"Unexpected Test #3 matrix IDs: {sorted(actual_ids)}"
    )

input_sha = sha256(INPUT_PATH)

frozen = copy.deepcopy(data)

frozen["reference_metadata"]["status"] = (
    "FROZEN_REFERENCE_V1"
)

frozen["reference_metadata"]["frozen_at_utc"] = (
    datetime.now(timezone.utc).isoformat()
)

frozen["reference_metadata"][
    "reference_input_sha256"
] = input_sha

frozen["reference_metadata"][
    "official_fault_injection_run_before_freeze"
] = False

frozen["freeze_manifest"] = {
    "reference_input_file": (
        "reference/reference_input_v1.json"
    ),
    "reference_input_sha256": input_sha,
    "official_fault_injection_output_used_for_freeze": False,
    "official_fault_injection_run_before_freeze": False,
    "expected_results_modified_after_run": False
}

OUTPUT_PATH.write_text(
    json.dumps(
        frozen,
        indent=2,
        ensure_ascii=False,
    )
    + "\n",
    encoding="utf-8",
)

print("TEST #3 REFERENCE FREEZE")
print("------------------------")
print("Status: FROZEN_REFERENCE_V1")
print("Reference input SHA256:", input_sha)
print("Frozen file:", OUTPUT_PATH)
print("Official fault injection run before freeze: NO")
