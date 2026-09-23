from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from time import perf_counter

from src.application.example_source_sets import (
    FORD_REAL_WORLD_SOURCE_SET,
    load_example_source_set,
)
from src.application.pdf_ingress import (
    build_semantic_document,
    ingest_pdf_document,
    rebind_pdf_document_role,
)
from src.application.pdf_vision_restore import (
    restore_pdf_document_from_vision_cache,
)
from src.application.semantic_ingress import (
    analyze_semantic_documents,
)


WORKERS = 4


def build_jobs():
    jobs = []

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

        for role in (
            "requirement",
            "verification",
        ):
            view = rebind_pdf_document_role(
                physical,
                role,
            )

            if not view.ready_for_semantic_analysis:
                raise RuntimeError(
                    f"{source.filename} [{role}] is not ready "
                    "for semantic analysis after Vision-cache restore."
                )

            if not view.full_document_coverage:
                raise RuntimeError(
                    f"{source.filename} [{role}] does not have "
                    "full document coverage."
                )

            semantic_document = (
                build_semantic_document(
                    view
                )
            )

            jobs.append(
                semantic_document
            )

    return jobs


def warm_one(document):
    started = perf_counter()

    result = analyze_semantic_documents(
        [document]
    )

    return {
        "source_name": document.source_name,
        "role": document.role,
        "elapsed": perf_counter() - started,
        "candidates": len(result.candidates),
    }


def main():
    jobs = build_jobs()

    print()
    print("FORD R/V SEMANTIC CACHE WARM-UP")
    print("==============================")
    print(f"Jobs    : {len(jobs)}")
    print(f"Workers : {WORKERS}")
    print()

    total_started = perf_counter()

    with ThreadPoolExecutor(
        max_workers=WORKERS
    ) as executor:
        futures = [
            executor.submit(
                warm_one,
                document,
            )
            for document in jobs
        ]

        completed = 0

        for future in as_completed(
            futures
        ):
            result = future.result()
            completed += 1

            print(
                f"[{completed}/{len(jobs)}] "
                f"{result['role']:12} "
                f"{result['source_name']} "
                f"| {result['elapsed']:.2f}s "
                f"| candidates="
                f"{result['candidates']}",
                flush=True,
            )

    print()
    print(
        "TOTAL:",
        f"{perf_counter() - total_started:.2f}s"
    )
    print("SEMANTIC_CACHE_WARMUP_COMPLETE")


if __name__ == "__main__":
    main()
