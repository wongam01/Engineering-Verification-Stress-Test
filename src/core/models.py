from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


# =========================================================
# HELPER
# =========================================================

def to_decimal(value: Any) -> Decimal:
    """
    int, float, str, Decimal 값을
    Engineering 계산용 Decimal로 변환한다.
    """

    if isinstance(value, Decimal):
        return value

    return Decimal(str(value))


# =========================================================
# VARIABLE MODEL
# =========================================================

@dataclass(frozen=True)
class VariableSpec:
    """
    하나의 Engineering Variable 정의.
    """

    unit: str

    nominal: Decimal

    feasible_min: Decimal
    feasible_max: Decimal

    verification_min: Decimal
    verification_max: Decimal

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "VariableSpec":

        return cls(
            unit=data["unit"],

            nominal=to_decimal(
                data["nominal"]
            ),

            feasible_min=to_decimal(
                data["feasible_min"]
            ),

            feasible_max=to_decimal(
                data["feasible_max"]
            ),

            verification_min=to_decimal(
                data["verification_min"]
            ),

            verification_max=to_decimal(
                data["verification_max"]
            ),
        )

    def to_dict(self) -> dict[str, Any]:

        return {
            "unit": self.unit,

            "nominal": self.nominal,

            "feasible_min": self.feasible_min,
            "feasible_max": self.feasible_max,

            "verification_min": (
                self.verification_min
            ),

            "verification_max": (
                self.verification_max
            ),
        }


# =========================================================
# GENERIC ENGINEERING CONSTRAINT
# =========================================================

@dataclass(frozen=True)
class ConstraintSpec:
    """
    Requirement와 Verification Constraint가
    공통으로 사용하는 Constraint 구조.

    현재 지원:

    1. range
    2. difference_min
    3. sum_upper
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
    ) -> "ConstraintSpec":

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

        if self.type == "range":

            if self.variable is None:
                return tuple()

            return (
                self.variable,
            )

        if self.type == "difference_min":

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

        # -------------------------------------------------
        # RANGE
        # -------------------------------------------------

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

        # -------------------------------------------------
        # DIFFERENCE MIN
        # -------------------------------------------------

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

        # -------------------------------------------------
        # SUM UPPER
        # -------------------------------------------------

        elif self.type == "sum_upper":

            data["variables"] = list(
                self.variables
            )

            data["limit"] = (
                self.limit
            )

        return data


# 기존 Core 코드와 호환하기 위한 이름
RequirementSpec = ConstraintSpec

# Verification Plan에서도 같은 구조 사용
VerificationConstraintSpec = ConstraintSpec


# =========================================================
# ENGINEERING CASE
# =========================================================

@dataclass
class EngineeringCase:
    """
    전체 Engineering Verification Case.

    requirements:
        실제 설계 / 기술 요구사항

    verification_constraints:
        기본 Variable Verification Range 외에
        Verification Plan에 추가되는 관계조건
    """

    name: str

    variables: dict[
        str,
        VariableSpec,
    ]

    requirements: list[
        ConstraintSpec
    ]

    verification_constraints: list[
        ConstraintSpec
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
            ConstraintSpec.from_dict(
                requirement_data
            )
            for requirement_data
            in data["requirements"]
        ]

        verification_constraints = [
            ConstraintSpec.from_dict(
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
    ) -> ConstraintSpec:

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
