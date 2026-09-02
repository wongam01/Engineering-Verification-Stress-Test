from dataclasses import dataclass

from z3 import (
    Optimize,
    sat,
    unsat,
)


# =========================================================
# DEFAULT POLICY
# =========================================================

DEFAULT_SOLVER_TIMEOUT_MS = 5000


# =========================================================
# SOLVER CHECK RESULT
# =========================================================

@dataclass(frozen=True)
class SolverCheckResult:
    """
    Z3 check 결과를 명시적으로 분류한다.
    """

    status: str
    reason: str | None = None

    @property
    def solved(self) -> bool:
        return self.status in {
            "SAT",
            "UNSAT",
        }

    @property
    def indeterminate(self) -> bool:
        return self.status == "UNKNOWN"


# =========================================================
# SOLVER INDETERMINATE ERROR
# =========================================================

class SolverIndeterminateError(
    RuntimeError
):
    """
    Z3가 timeout / incomplete 등의 이유로
    결정적인 답을 주지 못했음을 나타낸다.

    이 상태를 NO ESCAPE로 해석하면 안 된다.
    """

    def __init__(
        self,
        reason: str,
    ):
        self.reason = reason

        super().__init__(
            f"Solver indeterminate: {reason}"
        )


# =========================================================
# OPTIMIZER CREATION
# =========================================================

def create_optimizer(
    timeout_ms: int = DEFAULT_SOLVER_TIMEOUT_MS,
) -> Optimize:
    """
    모든 Stress Test에 동일한
    timeout policy를 적용한다.
    """

    if timeout_ms <= 0:
        raise ValueError(
            "timeout_ms must be greater than zero"
        )

    optimizer = Optimize()

    optimizer.set(
        timeout=timeout_ms
    )

    return optimizer


# =========================================================
# RAW CHECK
# =========================================================

def check_optimizer(
    optimizer,
) -> SolverCheckResult:
    """
    Z3 결과를 SAT / UNSAT / UNKNOWN으로
    명확하게 분리한다.
    """

    result = optimizer.check()

    if result == sat:
        return SolverCheckResult(
            status="SAT",
        )

    if result == unsat:
        return SolverCheckResult(
            status="UNSAT",
        )

    reason = None

    try:
        reason = (
            optimizer.reason_unknown()
        )
    except Exception:
        reason = None

    if not reason:
        reason = "unknown"

    return SolverCheckResult(
        status="UNKNOWN",
        reason=reason,
    )


# =========================================================
# DECISIVE CHECK
# =========================================================

def check_optimizer_decisive(
    optimizer,
):
    """
    기존 Stress Test 코드가 사용하는
    sat / unsat 비교 형식을 유지하면서,
    UNKNOWN은 예외로 올린다.

    따라서 timeout을 NO ESCAPE로
    잘못 해석할 수 없다.
    """

    result = check_optimizer(
        optimizer
    )

    if result.status == "UNKNOWN":
        raise SolverIndeterminateError(
            result.reason or "unknown"
        )

    if result.status == "SAT":
        return sat

    return unsat