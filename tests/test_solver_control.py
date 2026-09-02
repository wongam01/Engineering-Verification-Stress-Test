import unittest

from z3 import (
    Real,
)

from src.core.solver_control import (
    SolverCheckResult,
    check_optimizer,
    create_optimizer,
)


class FakeUnknownOptimizer:

    def __init__(
        self,
        reason,
    ):
        self.reason = reason

    def check(self):
        return object()

    def reason_unknown(self):
        return self.reason


class SolverControlTest(
    unittest.TestCase
):

    # =====================================================
    # SAT
    # =====================================================

    def test_01_sat_is_distinguished(
        self,
    ):
        optimizer = create_optimizer()

        x = Real("solver_control_sat_x")

        optimizer.add(
            x >= 0
        )

        result = check_optimizer(
            optimizer
        )

        self.assertEqual(
            result.status,
            "SAT",
        )

        self.assertTrue(
            result.solved
        )

        self.assertFalse(
            result.indeterminate
        )

    # =====================================================
    # UNSAT
    # =====================================================

    def test_02_unsat_is_distinguished(
        self,
    ):
        optimizer = create_optimizer()

        x = Real("solver_control_unsat_x")

        optimizer.add(
            x >= 10
        )

        optimizer.add(
            x <= 5
        )

        result = check_optimizer(
            optimizer
        )

        self.assertEqual(
            result.status,
            "UNSAT",
        )

        self.assertTrue(
            result.solved
        )

        self.assertFalse(
            result.indeterminate
        )

    # =====================================================
    # TIMEOUT / UNKNOWN
    # =====================================================

    def test_03_timeout_is_unknown(
        self,
    ):
        optimizer = FakeUnknownOptimizer(
            "timeout"
        )

        result = check_optimizer(
            optimizer
        )

        self.assertEqual(
            result.status,
            "UNKNOWN",
        )

        self.assertEqual(
            result.reason,
            "timeout",
        )

        self.assertFalse(
            result.solved
        )

        self.assertTrue(
            result.indeterminate
        )

    # =====================================================
    # GENERIC UNKNOWN
    # =====================================================

    def test_04_generic_unknown_is_preserved(
        self,
    ):
        optimizer = FakeUnknownOptimizer(
            "incomplete"
        )

        result = check_optimizer(
            optimizer
        )

        self.assertEqual(
            result.status,
            "UNKNOWN",
        )

        self.assertEqual(
            result.reason,
            "incomplete",
        )

    # =====================================================
    # INVALID TIMEOUT
    # =====================================================

    def test_05_invalid_timeout_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            create_optimizer(
                timeout_ms=0
            )

    # =====================================================
    # RESULT MODEL
    # =====================================================

    def test_06_unknown_result_is_indeterminate(
        self,
    ):
        result = SolverCheckResult(
            status="UNKNOWN",
            reason="timeout",
        )

        self.assertTrue(
            result.indeterminate
        )

        self.assertFalse(
            result.solved
        )


if __name__ == "__main__":
    unittest.main()