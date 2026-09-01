from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI


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

OUTPUT_FILE = REFERENCE_DIR / "adjudication_result.json"


TARGET_REQUIREMENT_IDS = [
    "NCPR 18",
    "NCPR 19",
    "NCPR 20",
    "NCPR 21",
    "NCPR 22",
    "NCPR 23",
    "NCPR 24",
    "NCPR 25",
    "NCPR 26",
    "NCPR 27",
    "NCPR 28",
    "NCPR 29",
]


ADJUDICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement_id": {
                        "type": "string",
                    },
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "AGREE",
                            "CONFLICT",
                            "AMBIGUOUS",
                            "NOT_FOUND",
                        ],
                    },
                    "source_location": {
                        "type": ["string", "null"],
                    },
                    "source_excerpt": {
                        "type": ["string", "null"],
                    },
                    "canonical_engineering_meaning": {
                        "type": ["string", "null"],
                    },
                    "canonical_semantic_categories": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "numeric_threshold",
                                "multiplier_relationship",
                                "coverage",
                                "sampling",
                                "logical_or",
                                "conditional",
                                "approval_governance",
                                "external_analysis",
                                "procedural",
                                "other",
                            ],
                        },
                    },
                    "canonical_constraints": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "coverage_or_condition": {
                        "type": ["string", "null"],
                    },
                    "run_a_source_supported": {
                        "type": "boolean",
                    },
                    "run_b_source_supported": {
                        "type": "boolean",
                    },
                    "substantive_difference": {
                        "type": "boolean",
                    },
                    "needs_human_review": {
                        "type": "boolean",
                    },
                    "review_reason": {
                        "type": ["string", "null"],
                    },
                },
                "required": [
                    "requirement_id",
                    "verdict",
                    "source_location",
                    "source_excerpt",
                    "canonical_engineering_meaning",
                    "canonical_semantic_categories",
                    "canonical_constraints",
                    "coverage_or_condition",
                    "run_a_source_supported",
                    "run_b_source_supported",
                    "substantive_difference",
                    "needs_human_review",
                    "review_reason",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "requirements",
    ],
    "additionalProperties": False,
}


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
        raise FileNotFoundError(path)

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def validate_required_files() -> None:
    required_files = [
        SOURCE_PDF,
        RUN_A_FILE,
        RUN_B_FILE,
        PRECHECK_FILE,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(
                f"Required validation file missing:\n{path}"
            )

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "The first adjudication result will not be overwritten."
        )


def validate_target_ids(
    adjudication: dict[str, Any],
) -> None:
    requirements = adjudication.get("requirements")

    if not isinstance(requirements, list):
        raise ValueError(
            "requirements must be a list"
        )

    returned_ids = [
        item.get("requirement_id")
        for item in requirements
        if isinstance(item, dict)
    ]

    expected = set(TARGET_REQUIREMENT_IDS)
    returned = set(returned_ids)

    missing = sorted(expected - returned)
    unexpected = sorted(returned - expected)

    if missing:
        raise ValueError(
            f"Adjudicator omitted IDs: {missing}"
        )

    if unexpected:
        raise ValueError(
            f"Adjudicator returned unexpected IDs: "
            f"{unexpected}"
        )

    if len(returned_ids) != len(
        TARGET_REQUIREMENT_IDS
    ):
        raise ValueError(
            "Adjudicator returned duplicate "
            "requirement IDs."
        )


def build_prompt(
    run_a: dict[str, Any],
    run_b: dict[str, Any],
    precheck: dict[str, Any],
) -> str:
    reference_a = json.dumps(
        run_a["candidate"],
        ensure_ascii=False,
        indent=2,
    )

    reference_b = json.dumps(
        run_b["candidate"],
        ensure_ascii=False,
        indent=2,
    )

    precheck_data = json.dumps(
        precheck["requirements"],
        ensure_ascii=False,
        indent=2,
    )

    return f"""
You are the independent source adjudicator for an engineering
validation benchmark.

You are given:

1. The original NASA source PDF.
2. Reference extraction Run A.
3. Independent reference extraction Run B.
4. A deterministic structural precheck.

You are NOT evaluating the prototype.

IMPORTANT INDEPENDENCE RULES:

- Prototype output is not available.
- Solver output is not available.
- Expected benchmark results are not available.
- Use the NASA PDF as the authoritative source.
- Run A and Run B are only candidate interpretations.
- Do not favor an interpretation merely because both AI runs agree.
- If both runs agree but the source does not support them,
  mark the appropriate conflict or ambiguity.
- Do not use outside engineering knowledge.
- Do not invent missing requirements.
- Preserve numerical values, units, inequality direction,
  coverage, sampling, logical alternatives, and conditions.
- Do not force procedural or external-analysis requirements
  into arithmetic constraints.
- source_excerpt must contain no more than 20 words.

VERDICT DEFINITIONS:

AGREE:
Run A and Run B express the same substantive engineering
meaning and that meaning is supported by the source.

CONFLICT:
Run A and Run B differ in a substantive engineering way,
or one/both contain a substantive interpretation contradicted
by the source.

AMBIGUOUS:
The source itself or the candidate interpretations cannot be
resolved confidently without human review.

NOT_FOUND:
The requested requirement cannot be supported from the source.

For AGREE:
needs_human_review should normally be false.

For CONFLICT, AMBIGUOUS, or NOT_FOUND:
needs_human_review must be true.

Create a source-grounded canonical interpretation for each
requirement. This canonical interpretation is a REFERENCE
CANDIDATE, not yet frozen ground truth.

Target IDs:
{", ".join(TARGET_REQUIREMENT_IDS)}

---------------- RUN A ----------------

{reference_a}

---------------- RUN B ----------------

{reference_b}

------------- PRECHECK ----------------

{precheck_data}
""".strip()


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    validate_required_files()

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not found."
        )

    model = os.getenv(
        "REFERENCE_ADJUDICATOR_MODEL",
        os.getenv(
            "REFERENCE_MODEL",
            "gpt-5.6-terra",
        ),
    )

    run_a = load_json(RUN_A_FILE)
    run_b = load_json(RUN_B_FILE)
    precheck = load_json(PRECHECK_FILE)

    source_sha256 = sha256_file(SOURCE_PDF)
    run_a_sha256 = sha256_file(RUN_A_FILE)
    run_b_sha256 = sha256_file(RUN_B_FILE)
    precheck_sha256 = sha256_file(PRECHECK_FILE)

    metadata_a = run_a.get(
        "reference_metadata",
        {},
    )
    metadata_b = run_b.get(
        "reference_metadata",
        {},
    )

    if (
        metadata_a.get("source_sha256")
        != source_sha256
    ):
        raise ValueError(
            "Run A source hash does not match "
            "the current NASA PDF."
        )

    if (
        metadata_b.get("source_sha256")
        != source_sha256
    ):
        raise ValueError(
            "Run B source hash does not match "
            "the current NASA PDF."
        )

    print(
        "=== NASA Reference Adjudicator ==="
    )
    print(f"Source SHA-256: {source_sha256}")
    print(f"Run A SHA-256: {run_a_sha256}")
    print(f"Run B SHA-256: {run_b_sha256}")
    print(f"Model: {model}")
    print()
    print("Uploading authoritative NASA source...")

    client = OpenAI(api_key=api_key)

    uploaded_file = None

    try:
        with SOURCE_PDF.open("rb") as pdf_file:
            uploaded_file = client.files.create(
                file=pdf_file,
                purpose="user_data",
            )

        print(
            f"Uploaded file ID: "
            f"{uploaded_file.id}"
        )
        print(
            "Running source-grounded adjudication..."
        )

        response = client.responses.create(
            model=model,
            store=False,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_file",
                            "file_id": uploaded_file.id,
                        },
                        {
                            "type": "input_text",
                            "text": build_prompt(
                                run_a,
                                run_b,
                                precheck,
                            ),
                        },
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": (
                        "nasa_reference_adjudication"
                    ),
                    "description": (
                        "Source-grounded adjudication "
                        "of two independent NASA "
                        "reference extractions."
                    ),
                    "strict": True,
                    "schema": ADJUDICATION_SCHEMA,
                }
            },
        )

        if not response.output_text:
            raise RuntimeError(
                "Adjudicator returned no output."
            )

        adjudication = json.loads(
            response.output_text
        )

        validate_target_ids(adjudication)

        artifact = {
            "adjudication_metadata": {
                "stage": (
                    "REFERENCE_ADJUDICATION"
                ),
                "created_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "source_file": str(
                    SOURCE_PDF.relative_to(
                        PROJECT_ROOT
                    )
                ),
                "source_sha256": source_sha256,
                "run_a_sha256": run_a_sha256,
                "run_b_sha256": run_b_sha256,
                "precheck_sha256": (
                    precheck_sha256
                ),
                "model": model,
                "response_id": response.id,
                "prototype_output_available": False,
                "solver_output_available": False,
                "expected_result_available": False,
                "frozen_ground_truth": False,
            },
            "adjudication": adjudication,
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

        requirements = adjudication[
            "requirements"
        ]

        agree = sum(
            item["verdict"] == "AGREE"
            for item in requirements
        )
        conflict = sum(
            item["verdict"] == "CONFLICT"
            for item in requirements
        )
        ambiguous = sum(
            item["verdict"] == "AMBIGUOUS"
            for item in requirements
        )
        not_found = sum(
            item["verdict"] == "NOT_FOUND"
            for item in requirements
        )
        human_review = sum(
            item["needs_human_review"]
            for item in requirements
        )

        print()
        print("=== ADJUDICATION SUMMARY ===")
        print(f"Total: {len(requirements)}")
        print(f"AGREE: {agree}")
        print(f"CONFLICT: {conflict}")
        print(f"AMBIGUOUS: {ambiguous}")
        print(f"NOT_FOUND: {not_found}")
        print(
            f"Human review required: "
            f"{human_review}"
        )
        print()

        for item in requirements:
            print(
                f"{item['requirement_id']}: "
                f"{item['verdict']}"
            )

            if item["needs_human_review"]:
                print(
                    "  Review:",
                    item["review_reason"],
                )

        print()
        print(f"Saved: {OUTPUT_FILE}")
        print()
        print(
            "This is still a reference candidate."
        )
        print(
            "No prototype result has been used."
        )

    finally:
        if uploaded_file is not None:
            try:
                client.files.delete(
                    uploaded_file.id
                )
                print()
                print(
                    "Temporary uploaded PDF deleted "
                    "from API storage."
                )
            except Exception as cleanup_error:
                print()
                print(
                    "WARNING: Temporary API file "
                    "cleanup failed:"
                )
                print(cleanup_error)


if __name__ == "__main__":
    main()