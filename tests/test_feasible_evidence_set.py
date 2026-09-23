import unittest
from types import SimpleNamespace

from src.application.feasible_evidence_ingress import (
    FeasibleEvidenceAnalysisResult,
)
from src.application.feasible_evidence_set import (
    analyze_feasible_evidence_documents,
)


class FeasibleEvidenceSetTest(unittest.TestCase):
    def test_empty_source_set_returns_none(self):
        result = analyze_feasible_evidence_documents(
            [],
            analyzer=lambda document: None,
        )

        self.assertIsNone(result)

    def test_multiple_sources_preserve_candidate_provenance(self):
        documents = [
            SimpleNamespace(
                content_sha256="a" * 64,
            ),
            SimpleNamespace(
                content_sha256="b" * 64,
            ),
        ]

        def fake_analyzer(document):
            source_hash = document.content_sha256

            return FeasibleEvidenceAnalysisResult(
                status="CANDIDATES_FOUND",
                source_name=source_hash[:4],
                source_sha256=source_hash,
                candidates=[
                    SimpleNamespace(
                        candidate_id=(
                            "feasible:"
                            + source_hash[:12]
                        ),
                        source_name=source_hash[:4],
                        source_sha256=source_hash,
                    )
                ],
            )

        result = analyze_feasible_evidence_documents(
            documents,
            analyzer=fake_analyzer,
        )

        self.assertEqual(
            len(result.candidates),
            2,
        )

        self.assertEqual(
            {
                candidate.source_sha256
                for candidate in result.candidates
            },
            {
                "a" * 64,
                "b" * 64,
            },
        )

    def test_duplicate_physical_source_is_analyzed_once(self):
        documents = [
            SimpleNamespace(
                content_sha256="a" * 64,
            ),
            SimpleNamespace(
                content_sha256="a" * 64,
            ),
        ]

        calls = []

        def fake_analyzer(document):
            calls.append(
                document.content_sha256
            )

            return FeasibleEvidenceAnalysisResult(
                status="NO_CANDIDATES",
                source_name="source",
                source_sha256=(
                    document.content_sha256
                ),
            )

        analyze_feasible_evidence_documents(
            documents,
            analyzer=fake_analyzer,
        )

        self.assertEqual(
            calls,
            ["a" * 64],
        )


if __name__ == "__main__":
    unittest.main()
