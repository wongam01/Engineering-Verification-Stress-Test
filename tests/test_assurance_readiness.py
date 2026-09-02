import unittest
from decimal import Decimal

from src.core.assurance_readiness import (
    check_feasible_domain_readiness,
)

from src.core.models import (
    FeasibleDomainEvidence,
    VariableSpec,
)


def make_variable(
    evidence=None,
):
    return VariableSpec(
        unit="bar",

        nominal=Decimal("5"),

        feasible_min=Decimal("4"),
        feasible_max=Decimal("6"),

        verification_min=Decimal("4"),
        verification_max=Decimal("6"),

        feasible_evidence=evidence,
    )


class AssuranceReadinessTest(
    unittest.TestCase
):

    # =====================================================
    # APPROVED
    # =====================================================

    def test_01_approved_evidence_is_ready(
        self,
    ):
        evidence = FeasibleDomainEvidence(
            source_type=(
                "operating_envelope"
            ),
            source_reference=(
                "Process Design Basis 4.2"
            ),
            approval_status="approved",
        )

        result = (
            check_feasible_domain_readiness(
                {
                    "P_out": make_variable(
                        evidence
                    )
                }
            )
        )

        self.assertTrue(
            result.ready
        )

        self.assertEqual(
            result.status,
            "READY",
        )

        self.assertEqual(
            result.issues,
            [],
        )

    # =====================================================
    # MISSING
    # =====================================================

    def test_02_missing_evidence_not_ready(
        self,
    ):
        result = (
            check_feasible_domain_readiness(
                {
                    "P_out": make_variable()
                }
            )
        )

        self.assertFalse(
            result.ready
        )

        self.assertEqual(
            result.status,
            "MISSING_EVIDENCE",
        )

        self.assertEqual(
            result.issues[0].code,
            "MISSING_EVIDENCE",
        )

    # =====================================================
    # UNREVIEWED
    # =====================================================

    def test_03_unreviewed_evidence_not_ready(
        self,
    ):
        evidence = FeasibleDomainEvidence(
            source_type=(
                "operating_envelope"
            ),
            source_reference=(
                "Process Design Basis 4.2"
            ),
            approval_status="unreviewed",
        )

        result = (
            check_feasible_domain_readiness(
                {
                    "P_out": make_variable(
                        evidence
                    )
                }
            )
        )

        self.assertFalse(
            result.ready
        )

        self.assertEqual(
            result.status,
            "UNREVIEWED_EVIDENCE",
        )

    # =====================================================
    # EMPTY SOURCE REFERENCE
    # =====================================================

    def test_04_empty_reference_is_invalid(
        self,
    ):
        evidence = FeasibleDomainEvidence(
            source_type=(
                "operating_envelope"
            ),
            source_reference="",
            approval_status="approved",
        )

        result = (
            check_feasible_domain_readiness(
                {
                    "P_out": make_variable(
                        evidence
                    )
                }
            )
        )

        self.assertFalse(
            result.ready
        )

        self.assertEqual(
            result.status,
            "INVALID_EVIDENCE",
        )

    # =====================================================
    # INVALID APPROVAL STATUS
    # =====================================================

    def test_05_unknown_approval_status_invalid(
        self,
    ):
        evidence = FeasibleDomainEvidence(
            source_type=(
                "operating_envelope"
            ),
            source_reference=(
                "Process Design Basis 4.2"
            ),
            approval_status="yes",
        )

        result = (
            check_feasible_domain_readiness(
                {
                    "P_out": make_variable(
                        evidence
                    )
                }
            )
        )

        self.assertFalse(
            result.ready
        )

        self.assertEqual(
            result.status,
            "INVALID_EVIDENCE",
        )

    # =====================================================
    # MULTIPLE VARIABLES
    # =====================================================

    def test_06_all_variables_must_be_approved(
        self,
    ):
        approved = FeasibleDomainEvidence(
            source_type=(
                "operating_envelope"
            ),
            source_reference=(
                "Process Design Basis 4.2"
            ),
            approval_status="approved",
        )

        unreviewed = FeasibleDomainEvidence(
            source_type=(
                "manufacturing_capability"
            ),
            source_reference=(
                "Capability Study MC-01"
            ),
            approval_status="unreviewed",
        )

        result = (
            check_feasible_domain_readiness(
                {
                    "P_out": make_variable(
                        approved
                    ),
                    "T_out": make_variable(
                        unreviewed
                    ),
                }
            )
        )

        self.assertFalse(
            result.ready
        )

        self.assertEqual(
            result.status,
            "UNREVIEWED_EVIDENCE",
        )

        self.assertEqual(
            len(result.issues),
            1,
        )

        self.assertEqual(
            result.issues[0].variable_name,
            "T_out",
        )

    # =====================================================
    # MULTIPLE ISSUE TYPES
    # =====================================================

    def test_07_all_issues_are_preserved(
        self,
    ):
        invalid = FeasibleDomainEvidence(
            source_type="",
            source_reference="",
            approval_status="approved",
        )

        result = (
            check_feasible_domain_readiness(
                {
                    "P_out": make_variable(),
                    "T_out": make_variable(
                        invalid
                    ),
                }
            )
        )

        self.assertFalse(
            result.ready
        )

        self.assertEqual(
            result.status,
            "INVALID_EVIDENCE",
        )

        codes = {
            issue.code
            for issue in result.issues
        }

        self.assertIn(
            "MISSING_EVIDENCE",
            codes,
        )

        self.assertIn(
            "INVALID_EVIDENCE",
            codes,
        )


if __name__ == "__main__":
    unittest.main()