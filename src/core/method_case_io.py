import json

from dataclasses import (
    MISSING,
    dataclass,
    fields,
)
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from src.core.method_checker import (
    MetricRequirement,
    MethodResult,
    check_method_disagreement,
)


# =========================================================
# CONSTANTS
# =========================================================

ALLOWED_METHOD_ROLES = {
    "current_verification",
    "cross_check",
    "unspecified",
}


# =========================================================
# ERROR
# =========================================================

class MethodCaseLoadError(ValueError):
    """
    Method Case JSON을 안전하게 Core 객체로
    변환할 수 없을 때 발생하는 오류.
    """

    pass


# =========================================================
# LOADED CASE
# =========================================================

@dataclass
class MethodCaseData:
    """
    JSON에서 읽어온 하나의 Method Comparison Case.

    requirement:
        비교 기준이 되는 Engineering Requirement

    methods:
        서로 다른 Verification / Analysis Method 결과
    """

    requirement: MetricRequirement
    methods: list[MethodResult]

    case_id: str | None = None
    case_name: str | None = None
    title: str | None = None
    source: str | None = None


# =========================================================
# JSON READER
# =========================================================

def _read_json(
    path: str | Path,
) -> dict[str, Any]:
    """
    JSON 파일을 읽고
    최상위 구조가 dictionary인지 확인한다.
    """

    json_path = Path(path)

    if not json_path.exists():
        raise MethodCaseLoadError(
            f"Method Case 파일을 찾을 수 없습니다: "
            f"{json_path}"
        )

    if not json_path.is_file():
        raise MethodCaseLoadError(
            f"Method Case 경로가 파일이 아닙니다: "
            f"{json_path}"
        )

    try:
        with json_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

    except json.JSONDecodeError as error:
        raise MethodCaseLoadError(
            "Method Case JSON 형식이 올바르지 않습니다. "
            f"line={error.lineno}, "
            f"column={error.colno}"
        ) from error

    except OSError as error:
        raise MethodCaseLoadError(
            f"Method Case 파일을 읽을 수 없습니다: "
            f"{json_path}"
        ) from error

    if not isinstance(data, dict):
        raise MethodCaseLoadError(
            "Method Case JSON의 최상위 구조는 "
            "object여야 합니다."
        )

    return data


# =========================================================
# KEY PICKER
# =========================================================

def _pick_section(
    data: dict[str, Any],
    primary_key: str,
    alias_key: str,
) -> Any:
    """
    JSON schema 이름이 조금 달라도
    명시적으로 허용한 alias만 처리한다.

    예:
        requirement
        metric_requirement

        methods
        method_results

    둘 다 동시에 있으면 모호하므로 실패한다.
    """

    has_primary = primary_key in data
    has_alias = alias_key in data

    if has_primary and has_alias:
        raise MethodCaseLoadError(
            f"'{primary_key}'와 "
            f"'{alias_key}'가 동시에 존재합니다. "
            "하나만 사용해야 합니다."
        )

    if has_primary:
        return data[primary_key]

    if has_alias:
        return data[alias_key]

    raise MethodCaseLoadError(
        f"필수 항목 '{primary_key}'가 없습니다."
    )


# =========================================================
# STRICT DATACLASS CONVERSION
# =========================================================

def _build_dataclass(
    cls,
    raw_data: Any,
    location: str,
):
    """
    JSON dictionary를 Core dataclass로 변환한다.

    안전성 원칙:

    1. object가 아니면 거부
    2. 알 수 없는 필드는 거부
    3. 필수 필드가 없으면 거부
    4. 생성 실패 시 명확한 오류 반환

    즉 malformed AI/JSON output을
    조용히 받아들이지 않는다.
    """

    if not isinstance(raw_data, dict):
        raise MethodCaseLoadError(
            f"{location}은 object여야 합니다."
        )

    dataclass_fields = fields(cls)

    allowed_fields = {
        field.name
        for field in dataclass_fields
    }

    unknown_fields = (
        set(raw_data.keys())
        - allowed_fields
    )

    if unknown_fields:
        unknown_text = ", ".join(
            sorted(unknown_fields)
        )

        raise MethodCaseLoadError(
            f"{location}에 알 수 없는 필드가 있습니다: "
            f"{unknown_text}"
        )

    required_fields = {
        field.name
        for field in dataclass_fields
        if (
            field.default is MISSING
            and
            field.default_factory is MISSING
        )
    }

    missing_fields = (
        required_fields
        - set(raw_data.keys())
    )

    if missing_fields:
        missing_text = ", ".join(
            sorted(missing_fields)
        )

        raise MethodCaseLoadError(
            f"{location}에 필수 필드가 없습니다: "
            f"{missing_text}"
        )

    normalized_data = dict(raw_data)

    # -----------------------------------------------------
    # DECIMAL NORMALIZATION
    # -----------------------------------------------------
    #
    # JSON에는 숫자가 문자열로 저장될 수 있지만,
    # Core에서는 Engineering numeric value를
    # Decimal로 유지한다.
    #
    # MetricRequirement.target
    # MethodResult.value
    #
    # 를 명시적으로 Decimal로 변환한다.
    # -----------------------------------------------------

    decimal_fields = set()

    if cls is MetricRequirement:
        decimal_fields.add("target")

    elif cls is MethodResult:
        decimal_fields.add("value")

    for field_name in decimal_fields:
        raw_value = normalized_data.get(
            field_name
        )

        if isinstance(raw_value, bool):
            raise MethodCaseLoadError(
                f"{location}.{field_name}은 "
                "숫자여야 합니다."
            )

        try:
            normalized_data[field_name] = (
                Decimal(str(raw_value))
            )

        except (
            InvalidOperation,
            ValueError,
            TypeError,
        ) as error:
            raise MethodCaseLoadError(
                f"{location}.{field_name}을 "
                "Decimal로 변환할 수 없습니다: "
                f"{raw_value!r}"
            ) from error

    try:
        return cls(**normalized_data)

    except (TypeError, ValueError) as error:
        raise MethodCaseLoadError(
            f"{location}을 "
            f"{cls.__name__}으로 변환할 수 없습니다: "
            f"{error}"
        ) from error


# =========================================================
# ROLE VALIDATION
# =========================================================

def _validate_method_roles(
    methods: list[MethodResult],
) -> None:
    """
    Method role이 허용된 값인지 확인한다.

    허용:
        current_verification
        cross_check
        unspecified
    """

    for index, method in enumerate(methods):
        role = method.role

        if role not in ALLOWED_METHOD_ROLES:
            raise MethodCaseLoadError(
                "허용되지 않은 Method role입니다. "
                f"methods[{index}].role = {role!r}"
            )


# =========================================================
# UNIT CONSISTENCY
# =========================================================

def _validate_unit_consistency(
    requirement: MetricRequirement,
    methods: list[MethodResult],
) -> None:
    """
    Requirement와 MethodResult 모두 unit 필드를
    가지고 있을 경우 단위 불일치를 차단한다.

    단위 변환을 추측하지 않는다.
    """

    requirement_unit = getattr(
        requirement,
        "unit",
        None,
    )

    if requirement_unit is None:
        return

    for index, method in enumerate(methods):
        method_unit = getattr(
            method,
            "unit",
            None,
        )

        if method_unit is None:
            continue

        if method_unit != requirement_unit:
            raise MethodCaseLoadError(
                "Requirement와 MethodResult의 "
                "unit이 일치하지 않습니다. "
                f"methods[{index}]: "
                f"{method_unit!r} != "
                f"{requirement_unit!r}"
            )


# =========================================================
# PUBLIC LOADER
# =========================================================

def load_method_case(
    path: str | Path,
) -> MethodCaseData:
    """
    Method Case JSON을 읽어서

        MetricRequirement
        MethodResult[]

    로 변환한다.
    """

    data = _read_json(path)

    requirement_data = _pick_section(
        data,
        "requirement",
        "metric_requirement",
    )

    methods_data = _pick_section(
        data,
        "methods",
        "method_results",
    )

    if not isinstance(methods_data, list):
        raise MethodCaseLoadError(
            "'methods'는 array여야 합니다."
        )

    if len(methods_data) == 0:
        raise MethodCaseLoadError(
            "'methods'가 비어 있습니다."
        )

    requirement = _build_dataclass(
        MetricRequirement,
        requirement_data,
        "requirement",
    )

    methods = []

    for index, raw_method in enumerate(
        methods_data
    ):
        method = _build_dataclass(
            MethodResult,
            raw_method,
            f"methods[{index}]",
        )

        methods.append(method)

    _validate_method_roles(methods)

    _validate_unit_consistency(
        requirement,
        methods,
    )

    return MethodCaseData(
        case_id=data.get("case_id"),
        case_name=data.get("case_name"),
        title=data.get("title"),
        source=data.get("source"),
        requirement=requirement,
        methods=methods,
    )


# =========================================================
# END-TO-END RUNNER
# =========================================================

def run_method_case(
    path: str | Path,
):
    """
    JSON
        ↓
    Loader
        ↓
    MetricRequirement / MethodResult
        ↓
    Role-aware Method Checker
        ↓
    Method Check Result
    """

    method_case = load_method_case(path)

    result = check_method_disagreement(
        method_case.requirement,
        method_case.methods,
    )

    return method_case, result


# =========================================================
# MANUAL E2E TEST
# =========================================================

def main():
    """
    CER Pipeline Dent 사례를 이용한
    간단한 End-to-End 실행.
    """

    path = Path(
        "samples/cer_dent_method_case.json"
    )

    print()
    print(
        "========================================"
    )
    print(
        " CER METHOD CASE END-TO-END TEST"
    )
    print(
        "========================================"
    )

    method_case, result = run_method_case(
        path
    )

    print()
    print(
        f"Case ID              : "
        f"{method_case.case_id}"
    )

    print(
        f"Loaded Methods       : "
        f"{len(method_case.methods)}"
    )

    print()

    for method in method_case.methods:
        method_name = method.method

        value = getattr(
            method,
            "value",
            None,
        )

        print(
            f"{method_name:<20} "
            f"{value} "
            f"[{method.role}]"
        )

    print()
    print(
        "----------------------------------------"
    )

    print(
        f"Method Disagreement     : "
        f"{result.disagreement_found}"
    )

    print(
        f"Indeterminate Found     : "
        f"{result.indeterminate_found}"
    )

    print(
        f"Verification Risk Found : "
        f"{result.verification_risk_found}"
    )

    print(
        "----------------------------------------"
    )

    expected = (
        result.disagreement_found is True
        and
        result.indeterminate_found is False
        and
        result.verification_risk_found is True
    )

    if expected:
        print(
            "METHOD CASE E2E TEST PASSED"
        )
    else:
        print(
            "METHOD CASE E2E TEST FAILED"
        )

    print()


if __name__ == "__main__":
    main()