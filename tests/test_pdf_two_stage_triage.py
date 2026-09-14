import unittest
from unittest.mock import patch

from src.ai import pdf_page_triage as triage


class PdfTwoStageTriageTest(unittest.TestCase):
    def test_01_small_candidate_set_goes_directly_to_focused_review(self):
        calls = []

        def fake_recommend(pdf_bytes, **kwargs):
            calls.append(kwargs)

            return triage.PdfPageTriageResult(
                selected_page_numbers=(4, 5, 6),
                reasons=(
                    (4, "dense numerical evidence"),
                    (5, "results table"),
                    (6, "annotated evidence"),
                ),
                summary="focused result",
            )

        with patch.object(
            triage,
            "recommend_pdf_pages_with_vision",
            side_effect=fake_recommend,
        ):
            result = triage.recommend_pdf_pages_two_stage(
                b"pdf",
                candidate_page_numbers=tuple(range(1, 23)),
                document_role="feasible",
                max_selected_pages=12,
                client=object(),
            )

        self.assertEqual(
            len(calls),
            1,
        )

        self.assertEqual(
            calls[0]["candidate_page_numbers"],
            tuple(range(1, 23)),
        )

        self.assertEqual(
            calls[0]["max_selected_pages"],
            12,
        )

        self.assertEqual(
            calls[0]["triage_mode"],
            "focused",
        )

        self.assertEqual(
            result.selected_page_numbers,
            (4, 5, 6),
        )

        self.assertIsNone(
            result.coarse_result
        )

        self.assertEqual(
            result.focused_result.selected_page_numbers,
            (4, 5, 6),
        )

    def test_02_large_candidate_set_uses_coarse_then_focused(self):
        calls = []

        def fake_recommend(pdf_bytes, **kwargs):
            calls.append(kwargs)

            if kwargs["triage_mode"] == "coarse":
                return triage.PdfPageTriageResult(
                    selected_page_numbers=tuple(
                        range(1, 25)
                    ),
                    reasons=(),
                    summary="coarse result",
                )

            return triage.PdfPageTriageResult(
                selected_page_numbers=(
                    2, 4, 5, 8, 12
                ),
                reasons=(),
                summary="focused result",
            )

        with patch.object(
            triage,
            "recommend_pdf_pages_with_vision",
            side_effect=fake_recommend,
        ):
            result = triage.recommend_pdf_pages_two_stage(
                b"pdf",
                candidate_page_numbers=tuple(range(1, 60)),
                document_role="requirement",
                max_selected_pages=12,
                client=object(),
            )

        self.assertEqual(
            len(calls),
            2,
        )

        coarse_call = calls[0]
        focused_call = calls[1]

        self.assertEqual(
            coarse_call["triage_mode"],
            "coarse",
        )

        self.assertEqual(
            coarse_call["candidate_page_numbers"],
            tuple(range(1, 60)),
        )

        self.assertEqual(
            coarse_call["max_selected_pages"],
            24,
        )

        self.assertEqual(
            focused_call["triage_mode"],
            "focused",
        )

        self.assertEqual(
            focused_call["candidate_page_numbers"],
            tuple(range(1, 25)),
        )

        self.assertEqual(
            focused_call["max_selected_pages"],
            12,
        )

        self.assertEqual(
            result.selected_page_numbers,
            (2, 4, 5, 8, 12),
        )

        self.assertIsNotNone(
            result.coarse_result
        )

    def test_03_focused_result_exposes_final_reasons_and_summary(self):
        focused = triage.PdfPageTriageResult(
            selected_page_numbers=(3,),
            reasons=(
                (3, "measurement table"),
            ),
            summary="final focused summary",
        )

        with patch.object(
            triage,
            "recommend_pdf_pages_with_vision",
            return_value=focused,
        ):
            result = triage.recommend_pdf_pages_two_stage(
                b"pdf",
                candidate_page_numbers=(1, 2, 3),
                document_role="verification",
                max_selected_pages=2,
                client=object(),
            )

        self.assertEqual(
            result.selected_page_numbers,
            (3,),
        )

        self.assertEqual(
            result.reasons,
            (
                (3, "measurement table"),
            ),
        )

        self.assertEqual(
            result.summary,
            "final focused summary",
        )

    def test_04_empty_coarse_result_fails_safe_before_focused_call(self):
        calls = []

        def fake_recommend(pdf_bytes, **kwargs):
            calls.append(kwargs)

            return triage.PdfPageTriageResult(
                selected_page_numbers=(),
                reasons=(),
                summary="nothing selected",
            )

        with patch.object(
            triage,
            "recommend_pdf_pages_with_vision",
            side_effect=fake_recommend,
        ):
            with self.assertRaises(ValueError):
                triage.recommend_pdf_pages_two_stage(
                    b"pdf",
                    candidate_page_numbers=tuple(
                        range(1, 60)
                    ),
                    document_role="feasible",
                    max_selected_pages=12,
                    client=object(),
                )

        self.assertEqual(
            len(calls),
            1,
        )


if __name__ == "__main__":
    unittest.main()
