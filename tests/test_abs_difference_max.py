import unittest

from src.core.models import (
    EngineeringCase,
)

from src.core.validator import (
    validate_case,
)

from src.core.stress_tester import (
    stress_test_case,
)

from src.core.patch_engine import (
    evaluate_patch_candidates,
    select_practical_patch,
)


class TestAbsDifferenceMax(unittest.TestCase):

    def make_case(
        self,
        limit="4",
        left="T_A",
        right="T_B",
        unit_a="degC",
        unit_b="degC",
        add_verification_relation=False,
    ):

        verification_constraints = []

        if add_verification_relation:

            verification_constraints.append(
                {
                    "id": "V_BALANCE",
                    "type": "abs_difference_max",
                    "unit": "degC",
                    "left": "T_A",
                    "right": "T_B",
                    "limit": "4",
                }
            )

        return EngineeringCase.from_dict(
            {
                "name": "ABS Difference Regression",

                "variables": {

                    "T_A": {
                        "unit": unit_a,
                        "nominal": "100",
                        "feasible_min": "95",
                        "feasible_max": "105",
                        "verification_min": "95",
                        "verification_max": "105",
                    },

                    "T_B": {
                        "unit": unit_b,
                        "nominal": "100",
                        "feasible_min": "95",
                        "feasible_max": "105",
                        "verification_min": "95",
                        "verification_max": "105",
                    },
                },

                "requirements": [
                    {
                        "id": "R_BALANCE",
                        "type": "abs_difference_max",
                        "unit": "degC",
                        "left": left,
                        "right": right,
                        "limit": limit,
                    }
                ],

                "verification_constraints": (
                    verification_constraints
                ),
            }
        )

    # =====================================================
    # 1. BLIND NUMERIC TEST
    #
    # limit을 기존 4가 아닌 3.37로 바꾼다.
    #
    # 최대 절대차 = 10
    # 예상 Worst Violation = 10 - 3.37 = 6.63
    # =====================================================

    def test_01_blind_limit_changes_result(self):

        case = self.make_case(
            limit="3.37"
        )

        validation = validate_case(case)

        self.assertTrue(
            validation.valid
        )

        result = stress_test_case(
            case
        )[0]

        self.assertTrue(
            result.escape_found
        )

        self.assertAlmostEqual(
            result.actual_value,
            10.0,
            places=9,
        )

        self.assertAlmostEqual(
            result.worst_violation,
            6.63,
            places=9,
        )

    # =====================================================
    # 2. LEFT / RIGHT SYMMETRY
    #
    # 절대값이므로
    #
    # |T_A - T_B|
    # ==
    # |T_B - T_A|
    # =====================================================

    def test_02_left_right_symmetry(self):

        case_ab = self.make_case(
            left="T_A",
            right="T_B",
        )

        case_ba = self.make_case(
            left="T_B",
            right="T_A",
        )

        result_ab = stress_test_case(
            case_ab
        )[0]

        result_ba = stress_test_case(
            case_ba
        )[0]

        self.assertTrue(
            result_ab.escape_found
        )

        self.assertTrue(
            result_ba.escape_found
        )

        self.assertAlmostEqual(
            result_ab.worst_violation,
            result_ba.worst_violation,
            places=9,
        )

        self.assertAlmostEqual(
            result_ab.actual_value,
            result_ba.actual_value,
            places=9,
        )

    # =====================================================
    # 3. SUFFICIENT VERIFICATION PLAN
    #
    # 검사계획 자체에
    # |T_A - T_B| <= 4
    # 를 넣으면 Escape가 없어야 한다.
    # =====================================================

    def test_03_verification_relation_closes_escape(self):

        case = self.make_case(
            add_verification_relation=True
        )

        validation = validate_case(case)

        self.assertTrue(
            validation.valid
        )

        result = stress_test_case(
            case
        )[0]

        self.assertFalse(
            result.escape_found
        )

    # =====================================================
    # 4. NEGATIVE LIMIT
    #
    # |A-B| <= -1
    #
    # 공학적으로 잘못된 입력이므로
    # Solver 전에 Validator가 차단해야 한다.
    # =====================================================

    def test_04_negative_limit_rejected(self):

        case = self.make_case(
            limit="-1"
        )

        validation = validate_case(case)

        self.assertFalse(
            validation.valid
        )

        messages = [
            issue.message
            for issue
            in validation.issues
        ]

        self.assertTrue(
            any(
                "음수" in message
                for message in messages
            )
        )

    # =====================================================
    # 5. UNIT MISMATCH
    #
    # T_A = degC
    # T_B = bar
    #
    # 관계식 계산 전에
    # Validator가 차단해야 한다.
    # =====================================================

    def test_05_unit_mismatch_rejected(self):

        case = self.make_case(
            unit_a="degC",
            unit_b="bar",
        )

        validation = validate_case(case)

        self.assertFalse(
            validation.valid
        )

        messages = [
            issue.message
            for issue
            in validation.issues
        ]

        self.assertTrue(
            any(
                "Unit 불일치" in message
                for message in messages
            )
        )

    # =====================================================
    # 6. PATCH + RE-ATTACK
    #
    # 자동 Patch가
    # 실제 Escape를 닫고
    # Nominal State도 유지해야 한다.
    # =====================================================

    def test_06_patch_closes_escape(self):

        case = self.make_case()

        before = stress_test_case(
            case
        )[0]

        self.assertTrue(
            before.escape_found
        )

        evaluations = (
            evaluate_patch_candidates(
                case,
                "R_BALANCE",
            )
        )

        selected = (
            select_practical_patch(
                evaluations
            )
        )

        self.assertIsNotNone(
            selected
        )

        self.assertTrue(
            selected.closes_escape
        )

        self.assertTrue(
            selected.preserves_nominal
        )

        self.assertTrue(
            selected.practical
        )

        after = stress_test_case(
            selected.patched_case
        )[0]

        self.assertFalse(
            after.escape_found
        )


if __name__ == "__main__":
    unittest.main()