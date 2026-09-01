from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parents[3]

SOURCE_PDF = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "source"
    / "NASA-SPEC-5022_Change2_Revalidated_2026.pdf"
)

OUTPUT_FILE = (
    PROJECT_ROOT
    / "validation"
    / "real_case_01_nasa"
    / "reference"
    / "candidate_run_a.json"
)


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


REFERENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "document_title": {
            "type": ["string", "null"],
        },
        "document_identifier": {
            "type": ["string", "null"],
        },
        "requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement_id": {
                        "type": "string",
                    },
                    "found": {
                        "type": "boolean",
                    },
                    "source_location": {
                        "type": ["string", "null"],
                    },
                    "source_excerpt": {
                        "type": ["string", "null"],
                    },
                    "engineering_meaning": {
                        "type": ["string", "null"],
                    },
                    "semantic_categories": {
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
                    "normalized_constraints": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                    "coverage_or_condition": {
                        "type": ["string", "null"],
                    },
                    "evidence_status": {
                        "type": "string",
                        "enum": [
                            "SUPPORTED_BY_SOURCE",
                            "AMBIGUOUS",
                            "NOT_FOUND",
                        ],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": [
                            "HIGH",
                            "MEDIUM",
                            "LOW",
                        ],
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
                    "found",
                    "source_location",
                    "source_excerpt",
                    "engineering_meaning",
                    "semantic_categories",
                    "normalized_constraints",
                    "coverage_or_condition",
                    "evidence_status",
                    "confidence",
                    "needs_human_review",
                    "review_reason",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "document_title",
        "document_identifier",
        "requirements",
    ],
    "additionalProperties": False,
}


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def validate_target_ids(candidate: dict) -> None:
    requirements = candidate.get("requirements")

    if not isinstance(requirements, list):
        raise ValueError("requirements must be a list")

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
            f"Reference AI omitted required target IDs: {missing}"
        )

    if unexpected:
        raise ValueError(
            f"Reference AI returned unexpected target IDs: {unexpected}"
        )

    if len(returned_ids) != len(TARGET_REQUIREMENT_IDS):
        raise ValueError(
            "Reference AI returned duplicate requirement IDs."
        )


def build_prompt() -> str:
    target_ids = ", ".join(TARGET_REQUIREMENT_IDS)

    return f"""
You are building an independent reference annotation from the attached
engineering source document.

IMPORTANT VALIDATION RULES:

1. Use ONLY the attached source PDF.
2. Do NOT use outside engineering knowledge.
3. Do NOT infer information that is not supported by the source.
4. Do NOT evaluate or imitate any prototype system.
5. You have NOT been given prototype outputs or expected solver results.
6. Extract the target requirement IDs exactly once each.
7. If an ID cannot be located or supported, set found=false and
   evidence_status=NOT_FOUND instead of guessing.
8. If the wording permits more than one reasonable interpretation,
   set evidence_status=AMBIGUOUS and needs_human_review=true.
9. source_excerpt must be a short source-grounding excerpt,
   no more than 20 words.
10. normalized_constraints are semantic normalization candidates only.
    Do not force a requirement into a mathematical form when the source
    is procedural, governance-related, conditional, or requires external
    engineering analysis.
11. Preserve inequality direction, units, multipliers, coverage,
    sampling meaning, logical OR, and IF/THEN conditions when present.
12. Do not determine whether our current solver supports the result.
    This task is source interpretation only.

Target requirement IDs:

{target_ids}

Return one entry for every target ID.
""".strip()


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    if not SOURCE_PDF.exists():
        raise FileNotFoundError(
            f"NASA source PDF not found:\n{SOURCE_PDF}"
        )

    if OUTPUT_FILE.exists():
        raise FileExistsError(
            f"{OUTPUT_FILE.name} already exists.\n"
            "Run A is preserved intentionally and will not be overwritten."
        )

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY was not found in the environment or .env file."
        )

    model = os.getenv(
        "REFERENCE_MODEL",
        "gpt-5.6-terra",
    )

    source_hash = sha256_file(SOURCE_PDF)

    print("=== NASA Reference Builder — Run A ===")
    print(f"Source: {SOURCE_PDF.name}")
    print(f"SHA-256: {source_hash}")
    print(f"Model: {model}")
    print(f"Targets: {len(TARGET_REQUIREMENT_IDS)}")
    print()
    print("Uploading source PDF...")

    client = OpenAI(api_key=api_key)

    uploaded_file = None

    try:
        with SOURCE_PDF.open("rb") as pdf_file:
            uploaded_file = client.files.create(
                file=pdf_file,
                purpose="user_data",
            )

        print(f"Uploaded file ID: {uploaded_file.id}")
        print("Running independent reference extraction...")

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
                            "text": build_prompt(),
                        },
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "nasa_reference_candidate",
                    "description": (
                        "Independent source-grounded reference annotation "
                        "for NASA NCPR requirements."
                    ),
                    "strict": True,
                    "schema": REFERENCE_SCHEMA,
                }
            },
        )

        if not response.output_text:
            raise RuntimeError(
                "Reference AI returned no output_text."
            )

        candidate = json.loads(response.output_text)

        validate_target_ids(candidate)

        artifact = {
            "reference_metadata": {
                "reference_stage": "CANDIDATE_RUN_A",
                "created_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "source_file": str(
                    SOURCE_PDF.relative_to(PROJECT_ROOT)
                ),
                "source_sha256": source_hash,
                "target_requirement_ids": TARGET_REQUIREMENT_IDS,
                "model": model,
                "response_id": response.id,
                "prototype_output_available_to_builder": False,
                "expected_solver_result_available_to_builder": False,
                "frozen": False,
            },
            "candidate": candidate,
        }

        OUTPUT_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        OUTPUT_FILE.write_text(
            json.dumps(
                artifact,
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

        print()
        print("Reference candidate created successfully.")
        print(f"Output: {OUTPUT_FILE}")
        print()
        print("IMPORTANT:")
        print("- This is NOT frozen ground truth yet.")
        print("- Prototype has NOT been executed.")
        print("- Run A will not be overwritten.")

    finally:
        if uploaded_file is not None:
            try:
                client.files.delete(uploaded_file.id)
                print()
                print("Temporary uploaded PDF deleted from API storage.")
            except Exception as cleanup_error:
                print()
                print(
                    "WARNING: Temporary API file cleanup failed:"
                )
                print(cleanup_error)


if __name__ == "__main__":
    main()