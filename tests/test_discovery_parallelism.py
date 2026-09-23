import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.application.feasible_evidence_set import (
    analyze_feasible_evidence_documents,
)
from src.application.role_grounding import (
    ground_feasible_candidates,
    ground_semantic_candidates,
)
from src.application.semantic_ingress import (
    analyze_semantic_documents,
)


class DiscoveryParallelismTest(unittest.TestCase):
    def test_semantic_extraction_can_run_in_parallel(self):
        barrier = threading.Barrier(
            2,
            timeout=2,
        )

        def extractor(
            text,
            role,
            source_name,
        ):
            barrier.wait()
            return []

        documents = [
            SimpleNamespace(
                role="requirement",
                text="A",
                source_name="a.pdf",
                source_sha256="a",
            ),
            SimpleNamespace(
                role="verification",
                text="B",
                source_name="b.pdf",
                source_sha256="b",
            ),
        ]

        result = analyze_semantic_documents(
            documents,
            extractor=extractor,
            max_workers=2,
        )

        self.assertEqual(
            result.status,
            "NO_SEMANTIC_CANDIDATES",
        )

    def test_feasible_extraction_can_run_in_parallel(self):
        barrier = threading.Barrier(
            2,
            timeout=2,
        )

        documents = [
            SimpleNamespace(
                content_sha256="a",
            ),
            SimpleNamespace(
                content_sha256="b",
            ),
        ]

        def analyzer(document):
            barrier.wait()

            return SimpleNamespace(
                source_sha256=(
                    document.content_sha256
                ),
                status="READY",
                candidates=[],
            )

        result = (
            analyze_feasible_evidence_documents(
                documents,
                analyzer=analyzer,
                max_workers=2,
            )
        )

        self.assertIsNotNone(result)
        self.assertEqual(
            result.status,
            "READY",
        )

    def test_semantic_grounding_can_run_in_parallel(self):
        barrier = threading.Barrier(
            2,
            timeout=2,
        )

        analysis = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    candidate_id="c1",
                    role="requirement",
                    source_text="A",
                    source_name="a.pdf",
                    adapter_accepted=True,
                    source_location_ready=True,
                ),
                SimpleNamespace(
                    candidate_id="c2",
                    role="verification",
                    source_text="B",
                    source_name="b.pdf",
                    adapter_accepted=True,
                    source_location_ready=True,
                ),
            ]
        )

        def fake_grounding(**kwargs):
            barrier.wait()

            return SimpleNamespace(
                status="SUPPORTED",
            )

        with patch(
            "src.application.role_grounding."
            "evaluate_candidate_role_grounding",
            side_effect=fake_grounding,
        ):
            result = ground_semantic_candidates(
                analysis,
                max_workers=2,
            )

        self.assertEqual(
            list(result),
            ["c1", "c2"],
        )

    def test_feasible_grounding_can_run_in_parallel(self):
        barrier = threading.Barrier(
            2,
            timeout=2,
        )

        analysis = SimpleNamespace(
            candidates=[
                SimpleNamespace(
                    candidate_id="f1",
                    source_text="A",
                    source_name="a.pdf",
                ),
                SimpleNamespace(
                    candidate_id="f2",
                    source_text="B",
                    source_name="b.pdf",
                ),
            ]
        )

        def fake_grounding(**kwargs):
            barrier.wait()

            return SimpleNamespace(
                status="SUPPORTED",
            )

        with patch(
            "src.application.role_grounding."
            "evaluate_candidate_role_grounding",
            side_effect=fake_grounding,
        ):
            result = ground_feasible_candidates(
                analysis,
                max_workers=2,
            )

        self.assertEqual(
            list(result),
            ["f1", "f2"],
        )


if __name__ == "__main__":
    unittest.main()
