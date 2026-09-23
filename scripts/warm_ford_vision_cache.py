from __future__ import annotations

import argparse

from src.ai.pdf_vision_cache import (
    default_vision_cache_dir,
    is_pdf_page_vision_cached,
    warm_pdf_page_vision_cache,
)
from src.application.example_source_sets import (
    FORD_REAL_WORLD_SOURCE_SET,
    load_example_source_set,
)
from src.application.pdf_ingress import (
    ingest_pdf_document,
    pdf_document_vision_candidate_page_numbers,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Warm persistent page-level Vision transcription "
            "cache for the Ford real-world source set."
        )
    )

    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Inspect cache coverage without calling Vision.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Maximum concurrent Vision calls. Default: 4.",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=4,
        help="Pages processed per resumable batch. Default: 4.",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if not 1 <= args.workers <= 8:
        raise SystemExit(
            "--workers must be between 1 and 8."
        )

    if args.batch_size < 1:
        raise SystemExit(
            "--batch-size must be at least 1."
        )

    sources = load_example_source_set(
        FORD_REAL_WORLD_SOURCE_SET
    )

    print()
    print("FORD DEEP VISION CACHE")
    print("======================")
    print("Cache:")
    print(default_vision_cache_dir())
    print()
    print(
        "Mode:",
        "STATUS ONLY"
        if args.status_only
        else "WARM CACHE",
    )
    print()

    source_states = []
    total_candidates = 0
    total_cached = 0
    total_pending = 0

    for source in sources:
        document = ingest_pdf_document(
            role="requirement",
            filename=source.filename,
            content=source.content,
        )

        candidate_pages = (
            pdf_document_vision_candidate_page_numbers(
                document
            )
        )

        cached_pages = tuple(
            page_number
            for page_number in candidate_pages
            if is_pdf_page_vision_cached(
                source.content,
                page_number=page_number,
            )
        )

        cached_set = set(cached_pages)

        pending_pages = tuple(
            page_number
            for page_number in candidate_pages
            if page_number not in cached_set
        )

        source_states.append(
            (
                source,
                document,
                candidate_pages,
                cached_pages,
                pending_pages,
            )
        )

        total_candidates += len(candidate_pages)
        total_cached += len(cached_pages)
        total_pending += len(pending_pages)

        print(source.filename)
        print(
            f"  total pages       : {document.total_pages}"
        )
        print(
            f"  Vision candidates : {len(candidate_pages)}"
        )
        print(
            f"  cached            : {len(cached_pages)}"
        )
        print(
            f"  pending           : {len(pending_pages)}"
        )
        print()

    print("SUMMARY")
    print("-------")
    print(
        f"Vision candidate pages : {total_candidates}"
    )
    print(
        f"Already cached         : {total_cached}"
    )
    print(
        f"Pending                : {total_pending}"
    )
    print()

    if args.status_only:
        print(
            "No Vision API calls were made."
        )
        return

    if total_pending == 0:
        print(
            "READY_FOR_DEMO_CACHE: YES"
        )
        return

    from src.ai.constraint_parser import (
        client as vision_client,
    )

    print(
        "Starting persistent Vision cache warm-up..."
    )
    print(
        "Completed batches are preserved if interrupted."
    )
    print()

    for (
        source,
        _document,
        _candidate_pages,
        _cached_pages,
        pending_pages,
    ) in source_states:

        if not pending_pages:
            continue

        print(
            f"▶ {source.filename}"
        )

        total_for_source = len(pending_pages)
        completed = 0

        for start in range(
            0,
            total_for_source,
            args.batch_size,
        ):
            batch = pending_pages[
                start:start + args.batch_size
            ]

            try:
                warm_pdf_page_vision_cache(
                    source.content,
                    page_numbers=batch,
                    client=vision_client,
                    max_workers=min(
                        args.workers,
                        len(batch),
                    ),
                )
            except Exception as exc:
                print()
                print(
                    "ERROR during Vision cache warm-up:"
                )
                print(exc)
                print()
                print(
                    "Previously completed pages remain cached."
                )
                print(
                    "Re-run the same command to resume."
                )
                raise

            completed += len(batch)

            print(
                f"  cached {completed:>3} / "
                f"{total_for_source} pending pages"
            )

        print()

    final_pending = 0

    for source in sources:
        document = ingest_pdf_document(
            role="requirement",
            filename=source.filename,
            content=source.content,
        )

        candidate_pages = (
            pdf_document_vision_candidate_page_numbers(
                document
            )
        )

        final_pending += sum(
            1
            for page_number in candidate_pages
            if not is_pdf_page_vision_cached(
                source.content,
                page_number=page_number,
            )
        )

    print("FINAL")
    print("-----")
    print(
        f"Pending Vision pages: {final_pending}"
    )
    print(
        "READY_FOR_DEMO_CACHE:",
        "YES" if final_pending == 0 else "NO",
    )


if __name__ == "__main__":
    main()
