from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


# =========================================================
# HELPER
# =========================================================

def to_decimal(value: Any) -> Decimal:
    """
    숫자를 Engineering 계산에 사용할
    Decimal 형식으로 변환한다.
    """

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


# =========================================================
# FEASIBLE DOMAIN EVIDENCE
# =========================================================

@dataclass(frozen=True)
class FeasibleDomainEvidence:
    """
    Feasible Domain의 출처와
    엔지니어 검토 상태를 보존한다.

    AI가 Feasible Domain을 임의로 결정하는 것이 아니라,
    실제 Engineering Evidence의 출처를
    추적하기 위한 모델이다.
    """

    source_type: str
    source_reference: str
    approval_status: str = "unreviewed"
    note: str | None = None

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "FeasibleDomainEvidence":

        return cls(
            source_type=data["source_type"],
            source_reference=data[
                "source_reference"
            ],
            approval_status=data.get(
                "approval_status",
                "unreviewed",
            ),
            note=data.get(
                "note"
            ),
        )

    def to_dict(self) -> dict[str, Any]:

        data = {
            "source_type": self.source_type,
            "source_reference": (
                self.source_reference
            ),
            "approval_status": (
                self.approval_status
            ),
        }

        if self.note is not None:
            data["note"] = self.note

        return data


# =========================================================
# VARIABLE
# =========================================================

@dataclass(frozen=True)
class VariableSpec:
    """
    하나의 Engineering 변수 정의.

    nominal:
        알려진 정상 / 기준 상태.
        실제 근거가 없는 경우 None을 허용한다.

    feasible_min / feasible_max:
        현실적으로 관측 또는 근거로 뒷받침되는
        Feasible Domain 범위.

    verification_min / verification_max:
        변수 자체에 정의된 기본 Verification bound.

        둘 다 존재:
            verification_min <= X <= verification_max

        min만 존재:
            X >= verification_min

        max만 존재:
            X <= verification_max

        둘 다 없음:
            변수 자체 Verification bound 없음.
            verification_constraints를 통해 별도 조건을
            정의할 수 있다.
    """

    unit: str
    nominal: Decimal | None
    feasible_min: Decimal
    feasible_max: Decimal
    verification_min: Decimal | None
    verification_max: Decimal | None
    feasible_evidence: (
        FeasibleDomainEvidence | None
    ) = None

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "VariableSpec":
        evidence_data = data.get(
            "feasible_evidence"
        )

        nominal = data.get("nominal")
        verification_minimum = data.get(
            "verification_min"
        )
        verification_maximum = data.get(
            "verification_max"
        )

        return cls(
            unit=data["unit"],
            nominal=(
                to_decimal(nominal)
                if nominal is not None
                else None
            ),
            feasible_min=to_decimal(
                data["feasible_min"]
            ),
            feasible_max=to_decimal(
                data["feasible_max"]
            ),
            verification_min=(
                to_decimal(
                    verification_minimum
                )
                if verification_minimum is not None
                else None
            ),
            verification_max=(
                to_decimal(
                    verification_maximum
                )
                if verification_maximum is not None
                else None
            ),
            feasible_evidence=(
                FeasibleDomainEvidence.from_dict(
                    evidence_data
                )
                if evidence_data is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data = {
            "unit": self.unit,
            "feasible_min": self.feasible_min,
            "feasible_max": self.feasible_max,
        }

        if self.nominal is not None:
            data["nominal"] = self.nominal

        if self.verification_min is not None:
            data["verification_min"] = (
                self.verification_min
            )

        if self.verification_max is not None:
            data["verification_max"] = (
                self.verification_max
            )

        if self.feasible_evidence is not None:
            data["feasible_evidence"] = (
                self.feasible_evidence.to_dict()
            )

        return data


# =========================================================
# ENGINEERING CONSTRAINT
# =========================================================

@dataclass(frozen=True)
class RequirementSpec:
    """
    하나의 Engineering 조건.

    현재 지원하는 조건:

    1. range
    2. difference_min
    3. sum_upper

    같은 구조를 설계 요구조건과
    검사계획 관계조건 모두에 사용할 수 있다.
    """

    id: str
    type: str
    unit: str

    description: str | None = None

    # range
    variable: str | None = None
    min_value: Decimal | None = None
    max_value: Decimal | None = None

    # difference_min
    left: str | None = None
    right: str | None = None

    # sum_upper
    variables: tuple[str, ...] = field(
        default_factory=tuple
    )

    limit: Decimal | None = None

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "RequirementSpec":

        minimum = data.get("min")
        maximum = data.get("max")
        limit = data.get("limit")

        return cls(
            id=data["id"],
            type=data["type"],
            unit=data["unit"],

            description=data.get(
                "description"
            ),

            variable=data.get(
                "variable"
            ),

            min_value=(
                to_decimal(minimum)
                if minimum is not None
                else None
            ),

            max_value=(
                to_decimal(maximum)
                if maximum is not None
                else None
            ),

            left=data.get(
                "left"
            ),

            right=data.get(
                "right"
            ),

            variables=tuple(
                data.get(
                    "variables",
                    [],
                )
            ),

            limit=(
                to_decimal(limit)
                if limit is not None
                else None
            ),
        )

    def referenced_variables(
        self,
    ) -> tuple[str, ...]:

        if self.type in {
            "range",
            "lower_bound",
            "upper_bound",
        }:

            if self.variable is None:
                return tuple()

            return (
                self.variable,
            )

        if self.type in {
            "difference_min",
            "abs_difference_max",
        }:

            result = []

            if self.left is not None:
                result.append(
                    self.left
                )

            if self.right is not None:
                result.append(
                    self.right
                )

            return tuple(result)

        if self.type == "sum_upper":

            return self.variables

        return tuple()

    def to_dict(self) -> dict[str, Any]:

        data = {
            "id": self.id,
            "type": self.type,
            "unit": self.unit,
        }

        if self.description is not None:

            data["description"] = (
                self.description
            )

        if self.type == "range":

            data["variable"] = (
                self.variable
            )

            data["min"] = (
                self.min_value
            )

            data["max"] = (
                self.max_value
            )

        elif self.type == "lower_bound":
            data["variable"] = (
                self.variable
            )
            data["min"] = (
                self.min_value
            )
        elif self.type == "upper_bound":
            data["variable"] = (
                self.variable
            )
            data["max"] = (
                self.max_value
            )
        elif self.type == "difference_min":

            data["left"] = (
                self.left
            )

            data["right"] = (
                self.right
            )

            data["min"] = (
                self.min_value
            )

        elif self.type == "abs_difference_max":

            data["left"] = (
                self.left
            )

            data["right"] = (
                self.right
            )

            data["limit"] = (
                self.limit
            )

        elif self.type == "sum_upper":

            data["variables"] = list(
                self.variables
            )

            data["limit"] = (
                self.limit
            )

        return data


# 같은 형태의 조건을 여러 곳에서 사용한다는 의미
ConstraintSpec = RequirementSpec


# =========================================================
# ENGINEERING CASE
# =========================================================

@dataclass
class EngineeringCase:
    """
    하나의 전체 Engineering 검증 Case.

    requirements:
        실제 설계 / 기술 요구조건

    verification_constraints:
        기본 검사 Range 외에
        검사계획에 들어가는 관계조건
    """

    name: str

    variables: dict[
        str,
        VariableSpec,
    ]

    requirements: list[
        RequirementSpec
    ]

    verification_constraints: list[
        RequirementSpec
    ] = field(
        default_factory=list
    )

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "EngineeringCase":

        variables = {}

        for (
            variable_name,
            variable_data,
        ) in data["variables"].items():

            variables[
                variable_name
            ] = VariableSpec.from_dict(
                variable_data
            )

        requirements = [
            RequirementSpec.from_dict(
                requirement_data
            )
            for requirement_data
            in data["requirements"]
        ]

        verification_constraints = [
            RequirementSpec.from_dict(
                constraint_data
            )
            for constraint_data
            in data.get(
                "verification_constraints",
                [],
            )
        ]

        return cls(
            name=data["name"],

            variables=variables,

            requirements=requirements,

            verification_constraints=(
                verification_constraints
            ),
        )

    def to_dict(self) -> dict[str, Any]:

        return {
            "name": self.name,

            "variables": {
                name: variable.to_dict()
                for (
                    name,
                    variable,
                ) in self.variables.items()
            },

            "requirements": [
                requirement.to_dict()
                for requirement
                in self.requirements
            ],

            "verification_constraints": [
                constraint.to_dict()
                for constraint
                in self.verification_constraints
            ],
        }

    def get_variable(
        self,
        name: str,
    ) -> VariableSpec:

        return self.variables[name]

    def get_requirement(
        self,
        requirement_id: str,
    ) -> RequirementSpec:

        for requirement in self.requirements:

            if (
                requirement.id
                == requirement_id
            ):

                return requirement

        raise KeyError(
            f"Unknown requirement: "
            f"{requirement_id}"
        )