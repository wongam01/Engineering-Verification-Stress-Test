from hashlib import sha256
from io import BytesIO
import unittest

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from src.application.pdf_ingress import (
    build_page_aware_text,
    build_pdf_page_preview,
    build_semantic_document,
    ingest_pdf_document,
    validate_pdf_document_set,
)
from src.application.semantic_ingress import (
    analyze_semantic_documents,
    apply_semantic_approvals,
    build_semantic_review_signature,
    confirm_ambiguous_source_location,
)
from src.application.variable_mapping import (
    apply_analysis_variable_mappings,
)
from src.core.models import EngineeringCase


def build_text_pdf(
    page_texts,
    *,
    password=None,
):
    writer = PdfWriter()

    for text in page_texts:
        page = writer.add_blank_page(
            width=612,
            height=792,
        )

        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_reference = writer._add_object(font)

        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): font_reference,
                    }
                )
            }
        )

        escaped = str(text).replace(
            "\\",
            "\\\\",
        ).replace(
            "(",
            "\\(",
        ).replace(
            ")",
            "\\)",
        )
        stream = DecodedStreamObject()
        stream.set_data(
            (
                "BT /F1 12 Tf 72 720 Td ("
                + escaped
                + ") Tj ET"
            ).encode("latin-1")
        )
        page[NameObject("/Contents")] = (
            writer._add_object(stream)
        )

    if password is not None:
        writer.encrypt(password)

    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def build_blank_pdf():
    writer = PdfWriter()
    writer.add_blank_page(
        width=612,
        height=792,
    )
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def constraint_extractor(
    text,
    role,
    source_name,
):
    if role == "requirement":
        source_text = (
            "R1. Hardness H shall be between 50 and 57 HRC."
        )
        return [
            {
                "source_line_id": "L2",
                "constraint_id": "R1",
                "type": "range",
                "unit": "HRC",
                "variable": "H",
                "min": "50",
                "max": "57",
                "left": None,
                "right": None,
                "variables": [],
                "limit": None,
                "needs_review": False,
                "review_reason": None,
                "source_text": source_text,
            }
        ]

    source_text = "V1. Accept when hardness H is at least 50 HRC."
    return [
        {
            "source_line_id": "L2",
            "constraint_id": "V1",
            "type": "lower_bound",
            "unit": "HRC",
            "variable": "H",
            "min": "50",
            "max": None,
            "left": None,
            "right": None,
            "variables": [],
            "limit": None,
            "needs_review": False,
            "review_reason": None,
            "source_text": source_text,
        }
    ]


def build_base_case():
    return EngineeringCase.from_dict(
        {
            "name": "PDF ingress case",
            "variables": {
                "H": {
                    "unit": "HRC",
                    "feasible_min": "58",
                    "feasible_max": "60",
                    "feasible_evidence": {
                        "source_type": "engineering_analysis",
                        "source_reference": "fixture:F_H",
                        "approval_status": "approved",
                    },
                }
            },
            "requirements": [],
            "verification_constraints": [],
        }
    )


class PdfIngressTest(unittest.TestCase):
    def test_01_multi_page_ingestion_preserves_identity_and_pages(self):
        raw = build_text_pdf(
            [
                "Cover page",
                "R1. Hardness H shall be between 50 and 57 HRC.",
            ]
        )

        document = ingest_pdf_document(
            role="requirement",
            filename="path/to/requirement.pdf",
            content=raw,
        )

        self.assertTrue(document.ready_for_semantic_analysis)
        self.assertEqual(document.filename, "requirement.pdf")
        self.assertEqual(document.content_sha256, sha256(raw).hexdigest())
        self.assertEqual(document.raw_bytes, raw)
        self.assertEqual(document.total_pages, 2)
        self.assertEqual(
            [page.page_number for page in document.pages],
            [1, 2],
        )

        page_aware = build_page_aware_text(document)
        self.assertIn("===== PDF PAGE 1 =====", page_aware)
        self.assertIn("===== PDF PAGE 2 =====", page_aware)

        semantic = build_semantic_document(document)
        self.assertEqual(semantic.source_format, "pdf")
        self.assertEqual(semantic.source_sha256, document.content_sha256)
        self.assertEqual(len(semantic.source_pages), 2)

        preview = build_pdf_page_preview(document, 2)
        self.assertIn(b"%PDF-", preview[:1024])

    def test_02_invalid_and_empty_pdf_fail_safe(self):
        invalid = ingest_pdf_document(
            role="requirement",
            filename="invalid.pdf",
            content=b"not a pdf",
        )
        empty = ingest_pdf_document(
            role="verification",
            filename="empty.pdf",
            content=b"",
        )

        self.assertEqual(invalid.status, "INVALID_PDF")
        self.assertFalse(invalid.ready_for_semantic_analysis)
        self.assertEqual(empty.status, "EMPTY_PDF")

    def test_03_image_only_pdf_is_explicitly_unsupported(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="scan.pdf",
            content=build_blank_pdf(),
        )

        self.assertEqual(
            document.status,
            "IMAGE_ONLY_OR_SCANNED_PDF_UNSUPPORTED",
        )
        self.assertFalse(document.ready_for_semantic_analysis)

    def test_04_encrypted_pdf_is_explicitly_unsupported(self):
        document = ingest_pdf_document(
            role="requirement",
            filename="encrypted.pdf",
            content=build_text_pdf(["R1. Secret"], password="secret"),
        )

        self.assertEqual(
            document.status,
            "ENCRYPTED_PDF_UNSUPPORTED",
        )

    def test_05_same_role_duplicate_is_blocked(self):
        raw = build_text_pdf(["R1. Requirement"])
        first = ingest_pdf_document(
            role="requirement",
            filename="one.pdf",
            content=raw,
        )
        second = ingest_pdf_document(
            role="requirement",
            filename="renamed.pdf",
            content=raw,
        )

        validation = validate_pdf_document_set([first, second])

        self.assertFalse(validation.valid)
        self.assertIn(
            "DUPLICATE_PDF_IN_ROLE",
            [issue.code for issue in validation.issues],
        )

    def test_06_same_pdf_across_roles_warns_but_is_allowed(self):
        raw = build_text_pdf(["R1 and V1 are in this document."])
        requirement = ingest_pdf_document(
            role="requirement",
            filename="combined.pdf",
            content=raw,
        )
        verification = ingest_pdf_document(
            role="verification",
            filename="combined.pdf",
            content=raw,
        )

        validation = validate_pdf_document_set(
            [requirement, verification]
        )

        self.assertTrue(validation.valid)
        self.assertEqual(
            validation.status,
            "PDF_DOCUMENT_SET_READY_WITH_WARNINGS",
        )
        self.assertIn(
            "PDF_REUSED_ACROSS_ROLES",
            [issue.code for issue in validation.issues],
        )

    def test_07_pdf_bytes_are_not_passed_to_extractor(self):
        raw = build_text_pdf(["R1. Requirement"])
        pdf = ingest_pdf_document(
            role="requirement",
            filename="requirement.pdf",
            content=raw,
        )
        semantic = build_semantic_document(pdf)
        observed = {}

        def extractor(text, role, source_name):
            observed["text"] = text
            observed["role"] = role
            return []

        analyze_semantic_documents(
            [semantic],
            extractor=extractor,
        )

        self.assertIsInstance(observed["text"], str)
        self.assertIn("===== PDF PAGE 1 =====", observed["text"])
        self.assertNotIn("%PDF-", observed["text"])
        self.assertEqual(observed["role"], "requirement")

    def test_08_unique_source_block_is_bound_to_exact_page(self):
        pdf = ingest_pdf_document(
            role="requirement",
            filename="requirement.pdf",
            content=build_text_pdf(
                [
                    "Cover page",
                    "R1. Hardness H shall be between 50 and 57 HRC.",
                ]
            ),
        )
        analysis = analyze_semantic_documents(
            [build_semantic_document(pdf)],
            extractor=constraint_extractor,
        )
        candidate = analysis.candidates[0]

        self.assertEqual(
            candidate.source_location_status,
            "SOURCE_LOCATION_RESOLVED",
        )
        self.assertEqual(candidate.source_page, 2)
        self.assertEqual(candidate.source_pages, (2,))
        self.assertTrue(candidate.source_location_ready)

    def test_09_ambiguous_location_requires_separate_human_confirmation(self):
        repeated = (
            "R1. Hardness H shall be between 50 and 57 HRC."
        )
        pdf = ingest_pdf_document(
            role="requirement",
            filename="repeated.pdf",
            content=build_text_pdf([repeated, repeated]),
        )
        analysis = analyze_semantic_documents(
            [build_semantic_document(pdf)],
            extractor=constraint_extractor,
        )
        candidate = analysis.candidates[0]

        self.assertEqual(
            candidate.source_location_status,
            "SOURCE_LOCATION_AMBIGUOUS",
        )
        self.assertEqual(
            candidate.source_location_candidates,
            (1, 2),
        )
        self.assertFalse(candidate.source_location_ready)

        blocked = apply_semantic_approvals(
            build_base_case(),
            analysis,
            [candidate.candidate_id],
        )
        self.assertFalse(blocked.ready_for_formal_workflow)

        confirmed = confirm_ambiguous_source_location(
            candidate,
            selected_page=2,
            confirmed=True,
        )

        self.assertEqual(
            confirmed.source_location_status,
            "SOURCE_LOCATION_HUMAN_CONFIRMED",
        )
        self.assertEqual(confirmed.source_page, 2)
        self.assertEqual(confirmed.source_pages, (2,))
        self.assertEqual(
            confirmed.source_location_review.selected_page,
            2,
        )
        self.assertEqual(confirmed.extraction, candidate.extraction)
        self.assertFalse(confirmed.approved)

        original_signature = build_semantic_review_signature(
            analysis,
            [candidate.candidate_id],
        )
        analysis.candidates[0] = confirmed
        reviewed_signature = build_semantic_review_signature(
            analysis,
            [candidate.candidate_id],
        )
        self.assertNotEqual(
            original_signature,
            reviewed_signature,
        )

    def test_10_unresolved_location_blocks_formalization(self):
        pdf = ingest_pdf_document(
            role="requirement",
            filename="requirement.pdf",
            content=build_text_pdf(["R1. Different source text."]),
        )
        analysis = analyze_semantic_documents(
            [build_semantic_document(pdf)],
            extractor=constraint_extractor,
        )
        candidate = analysis.candidates[0]
        ingress = apply_semantic_approvals(
            build_base_case(),
            analysis,
            [candidate.candidate_id],
        )

        self.assertEqual(
            candidate.source_location_status,
            "SOURCE_LOCATION_UNRESOLVED",
        )
        self.assertFalse(ingress.ready_for_formal_workflow)
        self.assertIn(
            "SOURCE_LOCATION_UNRESOLVED",
            "\n".join(ingress.issues),
        )

    def test_11_out_of_range_explicit_page_is_a_mismatch(self):
        pdf = ingest_pdf_document(
            role="requirement",
            filename="requirement.pdf",
            content=build_text_pdf(
                ["R1. Hardness H shall be between 50 and 57 HRC."]
            ),
        )

        def mismatched_extractor(text, role, source_name):
            result = constraint_extractor(text, role, source_name)[0]
            result["source_text"] = (
                "===== PDF PAGE 99 =====\n"
                "R1. Hardness H shall be between 50 and 57 HRC."
            )
            return [result]

        analysis = analyze_semantic_documents(
            [build_semantic_document(pdf)],
            extractor=mismatched_extractor,
        )

        self.assertEqual(
            analysis.candidates[0].source_location_status,
            "SOURCE_LOCATION_MISMATCH",
        )
        self.assertFalse(
            analysis.candidates[0].source_location_ready
        )

    def test_12_pdf_numeric_values_bind_without_manual_reentry(self):
        requirement_pdf = ingest_pdf_document(
            role="requirement",
            filename="requirement.pdf",
            content=build_text_pdf(
                ["R1. Hardness H shall be between 50 and 57 HRC."]
            ),
        )
        verification_pdf = ingest_pdf_document(
            role="verification",
            filename="verification.pdf",
            content=build_text_pdf(
                ["V1. Accept when hardness H is at least 50 HRC."]
            ),
        )
        analysis = analyze_semantic_documents(
            [
                build_semantic_document(requirement_pdf),
                build_semantic_document(verification_pdf),
            ],
            extractor=constraint_extractor,
        )
        mapped = apply_analysis_variable_mappings(
            analysis,
            {
                candidate.candidate_id: {"H": "H"}
                for candidate in analysis.candidates
            },
        )
        ingress = apply_semantic_approvals(
            build_base_case(),
            mapped,
            [candidate.candidate_id for candidate in mapped.candidates],
        )

        self.assertTrue(ingress.ready_for_formal_workflow)
        requirement = ingress.case.requirements[0]
        verification = ingress.case.verification_constraints[0]
        self.assertEqual(str(requirement.min_value), "50")
        self.assertEqual(str(requirement.max_value), "57")
        self.assertEqual(requirement.variable, "H")
        self.assertEqual(requirement.unit, "HRC")
        self.assertEqual(str(verification.min_value), "50")
        self.assertEqual(verification.variable, "H")
        self.assertEqual(verification.unit, "HRC")
        self.assertEqual(ingress.evidence[0].source_page, 1)
        self.assertEqual(
            ingress.evidence[0].source_sha256,
            requirement_pdf.content_sha256,
        )


    def test_13_feasible_pdf_role_is_ingested(self):
        raw = build_text_pdf(
            [
                (
                    "Measured production hardness H "
                    "ranged from 58 to 60 HRC."
                )
            ]
        )

        document = ingest_pdf_document(
            role="feasible",
            filename="Operating_Evidence.pdf",
            content=raw,
        )

        self.assertTrue(
            document.ready_for_semantic_analysis
        )
        self.assertEqual(
            document.role,
            "feasible",
        )
        self.assertEqual(
            document.filename,
            "Operating_Evidence.pdf",
        )
        self.assertIn(
            "58 to 60 HRC",
            build_page_aware_text(document),
        )

    def test_14_feasible_pdf_cannot_enter_rv_semantic_path(self):
        document = ingest_pdf_document(
            role="feasible",
            filename="Operating_Evidence.pdf",
            content=build_text_pdf(
                [
                    (
                        "Measured hardness H ranged "
                        "from 58 to 60 HRC."
                    )
                ]
            ),
        )

        with self.assertRaises(ValueError):
            build_semantic_document(
                document
            )

    def test_15_same_pdf_feasible_and_requirement_warns(self):
        raw = build_text_pdf(
            ["Shared engineering document."]
        )

        requirement = ingest_pdf_document(
            role="requirement",
            filename="shared.pdf",
            content=raw,
        )

        feasible = ingest_pdf_document(
            role="feasible",
            filename="shared.pdf",
            content=raw,
        )

        validation = validate_pdf_document_set(
            [
                requirement,
                feasible,
            ]
        )

        self.assertTrue(
            validation.valid
        )
        self.assertEqual(
            validation.status,
            "PDF_DOCUMENT_SET_READY_WITH_WARNINGS",
        )
        self.assertIn(
            "PDF_REUSED_ACROSS_ROLES",
            [
                issue.code
                for issue in validation.issues
            ],
        )


    def test_13_feasible_pdf_role_is_ingested(self):
        raw = build_text_pdf(
            [
                (
                    "Measured production hardness H "
                    "ranged from 58 to 60 HRC."
                )
            ]
        )

        document = ingest_pdf_document(
            role="feasible",
            filename="Operating_Evidence.pdf",
            content=raw,
        )

        self.assertTrue(
            document.ready_for_semantic_analysis
        )
        self.assertEqual(
            document.role,
            "feasible",
        )
        self.assertEqual(
            document.filename,
            "Operating_Evidence.pdf",
        )
        self.assertIn(
            "58 to 60 HRC",
            build_page_aware_text(document),
        )

    def test_14_feasible_pdf_cannot_enter_rv_semantic_path(self):
        document = ingest_pdf_document(
            role="feasible",
            filename="Operating_Evidence.pdf",
            content=build_text_pdf(
                [
                    (
                        "Measured hardness H ranged "
                        "from 58 to 60 HRC."
                    )
                ]
            ),
        )

        with self.assertRaises(ValueError):
            build_semantic_document(
                document
            )

    def test_15_same_pdf_feasible_and_requirement_warns(self):
        raw = build_text_pdf(
            ["Shared engineering document."]
        )

        requirement = ingest_pdf_document(
            role="requirement",
            filename="shared.pdf",
            content=raw,
        )

        feasible = ingest_pdf_document(
            role="feasible",
            filename="shared.pdf",
            content=raw,
        )

        validation = validate_pdf_document_set(
            [
                requirement,
                feasible,
            ]
        )

        self.assertTrue(
            validation.valid
        )
        self.assertEqual(
            validation.status,
            "PDF_DOCUMENT_SET_READY_WITH_WARNINGS",
        )
        self.assertIn(
            "PDF_REUSED_ACROSS_ROLES",
            [
                issue.code
                for issue in validation.issues
            ],
        )


if __name__ == "__main__":
    unittest.main()
