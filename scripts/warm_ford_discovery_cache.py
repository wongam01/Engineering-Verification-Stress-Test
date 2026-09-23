from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter

from src.application.example_source_sets import (
    FORD_REAL_WORLD_SOURCE_SET,
    load_example_source_set,
)
from src.application.feasible_evidence_set import (
    analyze_feasible_evidence_documents,
)
from src.application.pdf_ingress import (
    build_semantic_document,
    ingest_pdf_document,
    rebind_pdf_document_role,
)
from src.application.pdf_vision_restore import (
    restore_pdf_document_from_vision_cache,
)
from src.application.role_grounding import (
    ground_feasible_candidates,
    ground_semantic_candidates,
)
from src.application.semantic_ingress import (
    analyze_semantic_documents,
)


EXTRACTION_WORKERS = 4
GROUNDING_INNER_WORKERS = 2


def build_document_views():
    semantic_documents = []
    feasible_documents = []

    sources = load_example_source_set(
        FORD_REAL_WORLD_SOURCE_SET
    )

    for source in sources:
        physical = ingest_pdf_document(
            role="requirement",
            filename=source.filename,
            content=source.content,
        )

        physical = (
            restore_pdf_document_from_vision_cache(
                physical
            )
        )

        if not physical.ready_for_semantic_analysis:
            raise RuntimeError(
                f"{source.filename} is not ready "
                "after Vision-cache restore."
            )

        if not physical.full_document_coverage:
            raise RuntimeError(
                f"{source.filename} does not have "
                "full document coverage."
            )

        for role in (
            "requirement",
            "verification",
        ):
            view = rebind_pdf_document_role(
                physical,
                role,
            )

            semantic_documents.append(
                build_semantic_document(
                    view
                )
            )

        feasible_documents.append(
            rebind_pdf_document_role(
                physical,
                "feasible",
            )
        )

    return (
        semantic_documents,
        feasible_documents,
    )


def status_counts(results):
    return Counter(
        result.status
        for result in results.values()
    )


def main():
    print()
    print("FORD DISCOVERY CACHE WARM-UP")
    print()

    (
        semantic_documents,
        feasible_documents,
    ) = build_document_views()

    print(
        "R/V documents:",
        len(semantic_documents),
    )
    print(
        "F documents  :",
        len(feasible_documents),
    )
    print()

    total_started = perf_counter()

    started = perf_counter()

    semantic_analysis = (
        analyze_semantic_documents(
            semantic_documents,
            max_workers=EXTRACTION_WORKERS,
        )
    )

    semantic_elapsed = (
        perf_counter() - started
    )

    print(
        "[WARM] R/V extraction:",
        f"{semantic_elapsed:.2f}s",
        "| candidates=",
        len(semantic_analysis.candidates),
        sep="",
        flush=True,
    )

    started = perf_counter()

    feasible_analysis = (
        analyze_feasible_evidence_documents(
            feasible_documents,
            max_workers=EXTRACTION_WORKERS,
        )
    )

    feasible_elapsed = (
        perf_counter() - started
    )

    if feasible_analysis is None:
        raise RuntimeError(
            "Ford F analysis unexpectedly returned None."
        )

    print(
        "[WARM] F extraction: ",
        f"{feasible_elapsed:.2f}s",
        " | candidates=",
        len(feasible_analysis.candidates),
        sep="",
        flush=True,
    )

    def warm_semantic_grounding():
        started = perf_counter()

        results = ground_semantic_candidates(
            semantic_analysis,
            max_workers=GROUNDING_INNER_WORKERS,
        )

        return (
            results,
            perf_counter() - started,
        )

    def warm_feasible_grounding():
        started = perf_counter()

        results = ground_feasible_candidates(
            feasible_analysis,
            max_workers=GROUNDING_INNER_WORKERS,
        )

        return (
            results,
            perf_counter() - started,
        )

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        semantic_future = executor.submit(
            warm_semantic_grounding
        )

        feasible_future = executor.submit(
            warm_feasible_grounding
        )

        (
            semantic_grounding,
            semantic_grounding_elapsed,
        ) = semantic_future.result()

        (
            feasible_grounding,
            feasible_grounding_elapsed,
        ) = feasible_future.result()

    print(
        "[WARM] R/V grounding: ",
        f"{semantic_grounding_elapsed:.2f}s",
        " | candidates=",
        len(semantic_grounding),
        sep="",
        flush=True,
    )

    print(
        "[WARM] F grounding: ",
        f"{feasible_grounding_elapsed:.2f}s",
        " | candidates=",
        len(feasible_grounding),
        sep="",
        flush=True,
    )

    print()
    print(
        "R/V grounding status:",
        dict(
            status_counts(
                semantic_grounding
            )
        ),
    )

    print(
        "F grounding status  :",
        dict(
            status_counts(
                feasible_grounding
            )
        ),
    )

    print()

    hardness_candidates = [
        candidate
        for candidate in semantic_analysis.candidates
        if any(
            token in (
                candidate.source_text
                or ""
            ).lower()
            for token in (
                "hardness",
                "hrc",
                "50min",
                "50-57",
                "50 – 57",
            )
        )
    ]

    print(
        "Hardness-related R/V candidates:",
        len(hardness_candidates),
    )

    for candidate in hardness_candidates:
        grounding = semantic_grounding.get(
            candidate.candidate_id
        )

        if grounding is None:
            continue

        print(
            " -",
            candidate.role,
            "|",
            candidate.source_name,
            "|",
            candidate.extraction.get(
                "type"
            ),
            candidate.extraction.get(
                "min"
            ),
            candidate.extraction.get(
                "max"
            ),
            candidate.extraction.get(
                "unit"
            ),
            "|",
            grounding.status,
            "|",
            grounding.basis_type,
        )

    print()
    print(
        "TOTAL:",
        f"{perf_counter() - total_started:.2f}s",
    )
    print(
        "FORD_DISCOVERY_CACHE_WARMUP_COMPLETE"
    )


if __name__ == "__main__":
    main()
