import unittest
from pathlib import Path


APP = Path("src/ui/app.py")


class UiFeasibleScopeProvenanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = APP.read_text(encoding="utf-8")

    def test_01_rich_feasible_trace_builder_is_used(self):
        self.assertIn(
            "build_feasible_evidence_trace",
            self.text,
        )

    def test_02_prepared_feasible_traces_have_session_state(self):
        self.assertIn(
            '"prepared_feasible_evidence_traces"',
            self.text,
        )

    def test_03_prefill_is_converted_to_rich_trace(self):
        self.assertIn(
            "build_feasible_evidence_trace(prefill)",
            self.text,
        )

    def test_04_workflow_receives_prepared_feasible_traces(self):
        self.assertIn(
            'st.session_state["prepared_feasible_evidence_traces"]',
            self.text,
        )

        workflow_region = self.text[
            self.text.index(
                "run_verification_escape_workflow("
            ):
        ]

        self.assertIn(
            "prepared_feasible_evidence_traces",
            workflow_region,
        )


if __name__ == "__main__":
    unittest.main()
