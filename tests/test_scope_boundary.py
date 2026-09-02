import unittest

from src.core.json_io import (
    load_engineering_case,
)

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)

from src.core.scope_boundary import (
    assess_case_scope,
)


class ScopeBoundaryTest(
    unittest.TestCase
):

    # =====================================================
    # CURRENT HEATING SKID
    # =====================================================

    def test_01_heating_skid_is_supported(
        self,
    ):
        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        result = assess_case_scope(
            case
        )

        self.assertTrue(
            result.supported
        )

        self.assertEqual(
            result.status,
            "AUTOMATED_STRESS_TEST_SUPPORTED",
        )

        self.assertEqual(
            result.issues,
            [],
        )

    # =====================================================
    # UNKNOWN EXPLICIT CONSTRAINT
    # =====================================================

    def test_02_unknown_constraint_is_unsupported(
        self,
    ):
        requirement = RequirementSpec(
            id="R_UNKNOWN",
            type="custom_geometry_rule",
            unit="mm",
        )

        case = EngineeringCase(
            name="Unsupported Constraint Case",
            variables={},
            requirements=[
                requirement
            ],
        )

        result = assess_case_scope(
            case
        )

        self.assertFalse(
            result.supported
        )

        self.assertEqual(
            result.status,
            "UNSUPPORTED_CONSTRAINT",
        )

        self.assertEqual(
            result.issues[0].code,
            "UNSUPPORTED_CONSTRAINT",
        )

    # =====================================================
    # FEA
    # =====================================================

    def test_03_fea_requires_external_analysis(
        self,
    ):
        requirement = RequirementSpec(
            id="R_FEA",
            type="fea",
            unit="MPa",
        )

        case = EngineeringCase(
            name="FEA Case",
            variables={},
            requirements=[
                requirement
            ],
        )

        result = assess_case_scope(
            case
        )

        self.assertFalse(
            result.supported
        )

        self.assertEqual(
            result.status,
            "EXTERNAL_ANALYSIS_REQUIRED",
        )

    # =====================================================
    # FATIGUE
    # =====================================================

    def test_04_fatigue_requires_external_analysis(
        self,
    ):
        requirement = RequirementSpec(
            id="R_FATIGUE",
            type="fatigue_analysis",
            unit="years",
        )

        case = EngineeringCase(
            name="Fatigue Case",
            variables={},
            requirements=[
                requirement
            ],
        )

        result = assess_case_scope(
            case
        )

        self.assertFalse(
            result.supported
        )

        self.assertEqual(
            result.status,
            "EXTERNAL_ANALYSIS_REQUIRED",
        )

        self.assertEqual(
            result.issues[0].constraint_id,
            "R_FATIGUE",
        )

    # =====================================================
    # VERIFICATION CONSTRAINT ALSO CHECKED
    # =====================================================

    def test_05_verification_constraint_is_checked(
        self,
    ):
        verification = RequirementSpec(
            id="V_CFD",
            type="cfd",
            unit="m/s",
        )

        case = EngineeringCase(
            name="CFD Verification Case",
            variables={},
            requirements=[],
            verification_constraints=[
                verification
            ],
        )

        result = assess_case_scope(
            case
        )

        self.assertFalse(
            result.supported
        )

        self.assertEqual(
            result.status,
            "EXTERNAL_ANALYSIS_REQUIRED",
        )

        self.assertIn(
            "Verification Constraint",
            result.issues[0].location,
        )

    # =====================================================
    # UNKNOWN + EXTERNAL
    # =====================================================

    def test_06_unknown_has_priority_in_mixed_case(
        self,
    ):
        requirements = [
            RequirementSpec(
                id="R_FEA",
                type="fea",
                unit="MPa",
            ),
            RequirementSpec(
                id="R_UNKNOWN",
                type="mystery_rule",
                unit="mm",
            ),
        ]

        case = EngineeringCase(
            name="Mixed Scope Case",
            variables={},
            requirements=requirements,
        )

        result = assess_case_scope(
            case
        )

        self.assertFalse(
            result.supported
        )

        self.assertEqual(
            result.status,
            "UNSUPPORTED_CONSTRAINT",
        )

        self.assertEqual(
            len(result.issues),
            2,
        )


if __name__ == "__main__":
    unittest.main()