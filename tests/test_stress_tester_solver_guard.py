import unittest
from unittest.mock import patch

from src.core.json_io import (
    load_engineering_case,
)

from src.core.models import (
    EngineeringCase,
)

from src.core.solver_control import (
    SolverIndeterminateError,
)

from src.core.stress_tester import (
    stress_test_case,
    stress_test_requirement,
)


class StressTesterSolverGuardTest(
    unittest.TestCase
):

    def setUp(self):
        self.full_case = (
            load_engineering_case(
                "samples/heating_skid_case.json"
            )
        )

    # =====================================================
    # NORMAL ESCAPE
    # =====================================================

    def test_01_normal_escape_is_solved(
        self,
    ):
        requirement = (
            self.full_case.get_requirement(
                "R2"
            )
        )

        result = (
            stress_test_requirement(
                self.full_case,
                requirement,
            )
        )

        self.assertTrue(
            result.escape_found
        )

        self.assertEqual(
            result.solver_status,
            "SOLVED",
        )

    # =====================================================
    # NORMAL NO ESCAPE
    # =====================================================

    def test_02_normal_no_escape_is_solved(
        self,
    ):
        requirement = (
            self.full_case.get_requirement(
                "R1"
            )
        )

        result = (
            stress_test_requirement(
                self.full_case,
                requirement,
            )
        )

        self.assertFalse(
            result.escape_found
        )

        self.assertEqual(
            result.solver_status,
            "SOLVED",
        )

    # =====================================================
    # TIMEOUT
    # =====================================================

    def test_03_timeout_becomes_unknown(
        self,
    ):
        requirement = (
            self.full_case.get_requirement(
                "R2"
            )
        )

        case = EngineeringCase(
            name="Timeout Test Case",
            variables=(
                self.full_case.variables
            ),
            requirements=[
                requirement
            ],
            verification_constraints=(
                self.full_case
                .verification_constraints
            ),
        )

        with patch(
            "src.core.stress_tester."
            "check_optimizer_decisive",
            side_effect=(
                SolverIndeterminateError(
                    "timeout"
                )
            ),
        ):
            results = stress_test_case(
                case
            )

        self.assertEqual(
            len(results),
            1,
        )

        result = results[0]

        self.assertFalse(
            result.escape_found
        )

        self.assertEqual(
            result.solver_status,
            "UNKNOWN",
        )

        self.assertEqual(
            result.solver_reason,
            "timeout",
        )

    # =====================================================
    # OTHER UNKNOWN
    # =====================================================

    def test_04_incomplete_is_not_no_escape(
        self,
    ):
        requirement = (
            self.full_case.get_requirement(
                "R2"
            )
        )

        case = EngineeringCase(
            name="Incomplete Solver Case",
            variables=(
                self.full_case.variables
            ),
            requirements=[
                requirement
            ],
            verification_constraints=(
                self.full_case
                .verification_constraints
            ),
        )

        with patch(
            "src.core.stress_tester."
            "check_optimizer_decisive",
            side_effect=(
                SolverIndeterminateError(
                    "incomplete"
                )
            ),
        ):
            result = (
                stress_test_case(
                    case
                )[0]
            )

        self.assertEqual(
            result.solver_status,
            "UNKNOWN",
        )

        self.assertNotEqual(
            result.solver_status,
            "SOLVED",
        )

        self.assertEqual(
            result.solver_reason,
            "incomplete",
        )


if __name__ == "__main__":
    unittest.main()