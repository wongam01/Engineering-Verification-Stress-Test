import json
from decimal import Decimal
from pathlib import Path

from src.core.models import EngineeringCase


def load_engineering_case(
    file_path: str | Path,
) -> EngineeringCase:
    """
    JSON 파일을 읽어서 EngineeringCase로 변환한다.

    앞으로 AI가 생성한 JSON도
    이 함수를 통해 Core Engine으로 들어간다.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"JSON 파일을 찾을 수 없습니다: {path}"
        )

    if path.suffix.lower() != ".json":
        raise ValueError(
            "Engineering Case 입력은 JSON 파일이어야 합니다."
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        data = json.load(file)

    return EngineeringCase.from_dict(data)


def save_engineering_case(
    case: EngineeringCase,
    file_path: str | Path,
):
    """
    EngineeringCase를 JSON 파일로 저장한다.

    Decimal 값은 문자열로 변환하여
    소수점 값을 정확하게 보존한다.
    """

    path = Path(file_path)

    data = case.to_dict()

    serializable = _convert_for_json(data)

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            serializable,
            file,
            ensure_ascii=False,
            indent=2,
        )


def _convert_for_json(value):
    """
    Decimal / dict / list / tuple을
    JSON으로 저장 가능한 형태로 변환한다.
    """

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, dict):
        return {
            key: _convert_for_json(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            _convert_for_json(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            _convert_for_json(item)
            for item in value
        ]

    return value
