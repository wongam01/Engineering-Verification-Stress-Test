import unittest
from decimal import Decimal

from src.core.method_checker import (
    MetricRequirement,
    MethodResult,
    evaluate_method_result,
    check_method_disagreement,
)


class TestMethodChecker(unittest.TestCase):

    def make_requirement(
        self,
        target="150",
        operator=">=",
        unit="years",
    ):
        return MetricRequirement(
            metric="fatigue_life",
            operator=operator,
            target=Decimal(target),
            unit=unit,
        )

    def make_result(
        self,
        method,
        value,
        result_type="value",
        unit="years",
    ):
        return MethodResult(
            method=method,
            result_type=result_type,
            value=Decimal(value),
            unit=unit,
        )

    # =====================================================
    # 1. Exact value above target
    # =====================================================

    def test_exact_value_above_target_passes(self):

        requirement = self.make_requirement(
            target="150"
        )

        result = self.make_result(
            method="Method_A",
            value="200",
        )

        evaluation = evaluate_method_result(
            requirement,
            result,
        )

        self.assertEqual(
            evaluation.status,
            "PASS",
        )

    # =====================================================
    # 2. Exact value below target
    # =====================================================

    def test_exact_value_below_target_fails(self):

        requirement = self.make_requirement(
            target="150"
        )

        result = self.make_result(
            method="Method_A",
            value="130",
        )

        evaluation = evaluate_method_result(
            requirement,
            result,
        )

        self.assertEqual(
            evaluation.status,
            "FAIL",
        )

    # =====================================================
    # 3. Exact boundary = target
    # =====================================================

    def test_exact_value_equal_target_passes(self):

        requirement = self.make_requirement(
            target="150"
        )

        result = self.make_result(
            method="Method_A",
            value="150",
        )

        evaluation = evaluate_method_result(
            requirement,
            result,
        )

        self.assertEqual(
            evaluation.status,
            "PASS",
        )

    # =====================================================
    # 4. Lower bound above target
    # =====================================================

    def test_lower_bound_above_target_passes(self):

        requirement = self.make_requirement(
            target="150"
        )

        result = self.make_result(
            method="Method_A",
            value="308",
            result_type="lower_bound",
        )

        evaluation = evaluate_method_result(
            requirement,
            result,
        )

        self.assertEqual(
            evaluation.status,
            "PASS",
        )

    # =====================================================
    # 5. Lower bound below target
    #
    # >100 이라고만 알 때
    # 실제 값이 120인지 200인지 모르므로
    # FAIL이라고 단정하면 안 된다.
    # =====================================================

    def test_lower_bound_below_target_is_indeterminate(self):

        requirement = self.make_requirement(
            target="150"
        )

        result = self.make_result(
            method="Method_A",
            value="100",
            result_type="lower_bound",
        )

        evaluation = evaluate_method_result(
            requirement,
            result,
        )

        self.assertEqual(
            evaluation.status,
            "INDETERMINATE",
        )

    # =====================================================
    # 6. Lower bound boundary
    #
    # >150 이면 Requirement >=150을
    # 확실하게 만족한다.
    # =====================================================

    def test_lower_bound_equal_target_passes(self):

        requirement = self.make_requirement(
            target="150"
        )

        result = self.make_result(
            method="Method_A",
            value="150",
            result_type="lower_bound",
        )

        evaluation = evaluate_method_result(
            requirement,
            result,
        )

        self.assertEqual(
            evaluation.status,
            "PASS",
        )

    # =====================================================
    # 7. All methods PASS
    # =====================================================

    def test_all_methods_pass_no_disagreement(self):

        requirement = self.make_requirement()

        results = [
            self.make_result(
                "Method_A",
                "200",
            ),
            self.make_result(
                "Method_B",
                "180",
            ),
            self.make_result(
                "Method_C",
                "300",
            ),
        ]

        check = check_method_disagreement(
            requirement,
            results,
        )

        self.assertFalse(
            check.disagreement_found
        )

    # =====================================================
    # 8. PASS + FAIL
    # =====================================================

    def test_pass_and_fail_creates_disagreement(self):

        requirement = self.make_requirement()

        results = [
            self.make_result(
                "Method_A",
                "200",
            ),
            self.make_result(
                "Method_B",
                "130",
            ),
        ]

        check = check_method_disagreement(
            requirement,
            results,
        )

        self.assertTrue(
            check.disagreement_found
        )

    # =====================================================
    # 9. Unit mismatch
    # =====================================================

    def test_unit_mismatch_is_rejected(self):

        requirement = self.make_requirement(
            unit="years"
        )

        result = self.make_result(
            method="Method_A",
            value="200",
            unit="hours",
        )

        with self.assertRaises(
            ValueError
        ):
            evaluate_method_result(
                requirement,
                result,
            )

    # =====================================================
    # 10. Empty method results
    # =====================================================

    def test_empty_method_results_are_rejected(self):

        requirement = self.make_requirement()

        with self.assertRaises(
            ValueError
        ):
            check_method_disagreement(
                requirement,
                [],
            )



    # =====================================================
    # 11. PASS + INDETERMINATE
    # =====================================================

    def test_pass_and_indeterminate_are_distinguished(self):

        requirement = self.make_requirement()

        results = [
            self.make_result(
                "Method_A",
                "200",
            ),
            self.make_result(
                "Method_B",
                "100",
                result_type="lower_bound",
            ),
        ]

        check = check_method_disagreement(
            requirement,
            results,
        )

        self.assertFalse(
            check.disagreement_found
        )

        self.assertTrue(
            check.indeterminate_found
        )

    # =====================================================
    # 12. PASS + FAIL + INDETERMINATE
    # =====================================================

    def test_disagreement_and_indeterminate_can_coexist(self):

        requirement = self.make_requirement()

        results = [
            self.make_result(
                "Method_A",
                "200",
            ),
            self.make_result(
                "Method_B",
                "130",
            ),
            self.make_result(
                "Method_C",
                "100",
                result_type="lower_bound",
            ),
        ]

        check = check_method_disagreement(
            requirement,
            results,
        )

        self.assertTrue(
            check.disagreement_found
        )

        self.assertTrue(
            check.indeterminate_found
        )



    # =====================================================
    # 13. Current PASS + Cross-check FAIL
    # =====================================================

    def test_current_pass_and_cross_check_fail_creates_risk(self):

        requirement = self.make_requirement()

        results = [
            MethodResult(
                method="Current_Method",
                result_type="value",
                value=Decimal("200"),
                unit="years",
                role="current_verification",
            ),
            MethodResult(
                method="Cross_Check",
                result_type="value",
                value=Decimal("130"),
                unit="years",
                role="cross_check",
            ),
        ]

        check = check_method_disagreement(
            requirement,
            results,
        )

        self.assertTrue(
            check.disagreement_found
        )

        self.assertTrue(
            check.verification_risk_found
        )

    # =====================================================
    # 14. Current FAIL + Cross-check PASS
    #
    # 결과 충돌은 있지만,
    # "현재 Verification이 잘못 PASS시킨 위험"
    # 상황은 아니다.
    # =====================================================

    def test_current_fail_and_cross_check_pass_is_not_verification_risk(self):

        requirement = self.make_requirement()

        results = [
            MethodResult(
                method="Current_Method",
                result_type="value",
                value=Decimal("130"),
                unit="years",
                role="current_verification",
            ),
            MethodResult(
                method="Cross_Check",
                result_type="value",
                value=Decimal("200"),
                unit="years",
                role="cross_check",
            ),
        ]

        check = check_method_disagreement(
            requirement,
            results,
        )

        self.assertTrue(
            check.disagreement_found
        )

        self.assertFalse(
            check.verification_risk_found
        )

    # =====================================================
    # 15. Role 미지정
    #
    # PASS/FAIL 충돌은 감지하지만,
    # 어느 것이 Current Verification인지 모르므로
    # Verification Risk라고 단정하지 않는다.
    # =====================================================

    def test_unspecified_roles_do_not_create_verification_risk(self):

        requirement = self.make_requirement()

        results = [
            self.make_result(
                "Method_A",
                "200",
            ),
            self.make_result(
                "Method_B",
                "130",
            ),
        ]

        check = check_method_disagreement(
            requirement,
            results,
        )

        self.assertTrue(
            check.disagreement_found
        )

        self.assertFalse(
            check.verification_risk_found
        )


if __name__ == "__main__":
    unittest.main()