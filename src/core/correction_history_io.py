import json
from pathlib import Path

from src.core.correction_history import (
    CorrectionRecord,
)


# =========================================================
# SERIALIZATION
# =========================================================

def correction_record_to_dict(
    record: CorrectionRecord,
) -> dict:
    """
    CorrectionRecord를
    JSON 저장 가능한 dict로 변환한다.
    """

    return {
        "target_type": (
            record.target_type
        ),
        "source_text": (
            record.source_text
        ),
        "corrected_value": (
            record.corrected_value
        ),
        "decision": (
            record.decision
        ),
        "reviewer_reference": (
            record.reviewer_reference
        ),
        "reviewed_at": (
            record.reviewed_at
        ),
        "note": (
            record.note
        ),
    }


# =========================================================
# DESERIALIZATION
# =========================================================

def correction_record_from_dict(
    data: dict,
) -> CorrectionRecord:
    """
    JSON dict를 CorrectionRecord로 변환한다.

    필요한 필드가 없거나
    잘못된 형태면 명확하게 거부한다.
    """

    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Correction record must be an object."
        )

    required_fields = {
        "target_type",
        "source_text",
        "corrected_value",
        "decision",
    }

    missing = (
        required_fields
        - data.keys()
    )

    if missing:
        raise ValueError(
            "Missing correction record fields: "
            + ", ".join(
                sorted(missing)
            )
        )

    allowed_fields = {
        "target_type",
        "source_text",
        "corrected_value",
        "decision",
        "reviewer_reference",
        "reviewed_at",
        "note",
    }

    unknown = (
        data.keys()
        - allowed_fields
    )

    if unknown:
        raise ValueError(
            "Unknown correction record fields: "
            + ", ".join(
                sorted(unknown)
            )
        )

    string_fields = {
        "target_type",
        "source_text",
        "corrected_value",
        "decision",
    }

    for field_name in string_fields:

        value = data[
            field_name
        ]

        if not isinstance(
            value,
            str,
        ):
            raise ValueError(
                f"{field_name} must be a string."
            )

        if not value.strip():
            raise ValueError(
                f"{field_name} must not be empty."
            )

    optional_string_fields = {
        "reviewer_reference",
        "reviewed_at",
        "note",
    }

    for field_name in (
        optional_string_fields
    ):
        value = data.get(
            field_name
        )

        if (
            value is not None
            and
            not isinstance(
                value,
                str,
            )
        ):
            raise ValueError(
                f"{field_name} must be "
                "a string or null."
            )

    return CorrectionRecord(
        target_type=(
            data["target_type"]
        ),
        source_text=(
            data["source_text"]
        ),
        corrected_value=(
            data["corrected_value"]
        ),
        decision=(
            data["decision"]
        ),
        reviewer_reference=(
            data.get(
                "reviewer_reference"
            )
        ),
        reviewed_at=(
            data.get(
                "reviewed_at"
            )
        ),
        note=(
            data.get(
                "note"
            )
        ),
    )


# =========================================================
# SAVE
# =========================================================

def save_correction_history(
    path: str | Path,
    records: list[
        CorrectionRecord
    ],
) -> None:
    """
    Correction History를 JSON으로 저장한다.
    """

    output_path = Path(
        path
    )

    payload = {
        "schema_version": 1,
        "records": [
            correction_record_to_dict(
                record
            )
            for record
            in records
        ],
    }

    output_path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


# =========================================================
# LOAD
# =========================================================

def load_correction_history(
    path: str | Path,
) -> list[CorrectionRecord]:
    """
    Correction History JSON을 읽고
    검증한 뒤 Record 목록으로 반환한다.
    """

    input_path = Path(
        path
    )

    try:
        raw = input_path.read_text(
            encoding="utf-8"
        )

    except OSError as exc:
        raise ValueError(
            "Correction history file "
            "could not be read."
        ) from exc

    try:
        payload = json.loads(
            raw
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "Correction history is not valid JSON."
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Correction history root "
            "must be an object."
        )

    allowed_root_fields = {
        "schema_version",
        "records",
    }

    unknown_root_fields = (
        payload.keys()
        - allowed_root_fields
    )

    if unknown_root_fields:
        raise ValueError(
            "Unknown correction history fields: "
            + ", ".join(
                sorted(
                    unknown_root_fields
                )
            )
        )

    if (
        payload.get(
            "schema_version"
        )
        != 1
    ):
        raise ValueError(
            "Unsupported correction history "
            "schema version."
        )

    records_data = payload.get(
        "records"
    )

    if not isinstance(
        records_data,
        list,
    ):
        raise ValueError(
            "Correction history records "
            "must be a list."
        )

    return [
        correction_record_from_dict(
            item
        )
        for item
        in records_data
    ]