from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


# =========================================================
# HELPER
# =========================================================

def to_decimal(value: Any) -> Decimal:
    """
    int, float, str, Decimal 값을
    Engineering 계산에 사용할 Decimal로 변환한다.

    float도 str()을 거쳐 변환하여
    불필요한 부동소수점 오차를 줄인다.
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

    예:
        X
        Y
        Diameter
        Temperature
        Load_1
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
        """
        기존 Prototype에서 사용하던
        dictionary 형식을 VariableSpec으로 변환한다.
        """

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
        """
        기존 Prototype 형식과 호환되는
        dictionary로 변환한다.
        """

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
# REQUIREMENT MODEL
# =========================================================

@dataclass(frozen=True)
class RequirementSpec:
    """
    하나의 Engineering Requirement 정의.

    현재 Prototype에서 지원하는 Type:

    1. range
    2. difference_min
    3. sum_upper

    Constraint Type마다 필요한 필드가 다르기 때문에
    사용하지 않는 값은 None으로 둔다.
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

    # sum_upper limit
    limit: Decimal | None = None

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "RequirementSpec":
        """
        기존 Requirement dictionary를
        공통 RequirementSpec으로 변환한다.
        """

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
        """
        이 Requirement가 실제로 참조하는
        Engineering Variable 이름을 반환한다.
        """

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
        """
        기존 Prototype 형식과 호환되는
        dictionary로 변환한다.
        """

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


# =========================================================
# ENGINEERING CASE MODEL
# =========================================================

@dataclass
class EngineeringCase:
    """
    Verification Stress Test의
    전체 Engineering Case.

    앞으로 Validator, Solver, Patch Engine이
    모두 이 구조를 공통으로 사용한다.
    """

    name: str

    variables: dict[
        str,
        VariableSpec,
    ]

    requirements: list[
        RequirementSpec
    ]

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
    ) -> "EngineeringCase":
        """
        기존 CASE dictionary를
        EngineeringCase 객체로 변환한다.
        """

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

        requirements = []

        for requirement_data in data[
            "requirements"
        ]:

            requirements.append(
                RequirementSpec.from_dict(
                    requirement_data
                )
            )

        return cls(
            name=data["name"],
            variables=variables,
            requirements=requirements,
        )

    def to_dict(self) -> dict[str, Any]:
        """
        EngineeringCase를 기존 Prototype과
        호환되는 dictionary로 변환한다.

        Core Refactoring 중 기존 코드와
        연결할 때 사용할 수 있다.
        """

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
        }

    def get_variable(
        self,
        name: str,
    ) -> VariableSpec:
        """
        변수 이름으로 VariableSpec을 가져온다.
        """

        return self.variables[name]

    def get_requirement(
        self,
        requirement_id: str,
    ) -> RequirementSpec:
        """
        Requirement ID로 Requirement를 찾는다.
        """

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