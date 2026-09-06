import argparse
import hashlib
import importlib.util
import inspect
import io
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


REFERENCE_PATH = (
    ROOT
    / "validation/fault_injection_03/reference/reference_v1.json"
)

EXPECTED_REFERENCE_SHA256 = (
    "3b5180fe264e031fd7b7e523910986338"
    "7e3ce1f81f9e96fb7ef84e4d0cc9586"
)

EXPECTED_REFERENCE_INPUT_SHA256 = (
    "e5badf4e265c27c7fd89ce99b7932125"
    "d64433655758056e55c9b5f1e715b37c"
)


CASE_PLAN = [
    {
        "id": "T3-01",
        "fault": "unsupported_constraint_semantics",
        "exact": [
            (
                "tests/test_assured_pipeline_scope.py",
                "test_02_unknown_constraint_blocks_core",
            ),
        ],
        "selectors": [],
    },
    {
        "id": "T3-02",
        "fault": "external_analysis_required",
        "exact": [
            (
                "tests/test_assured_pipeline_scope.py",
                "test_01_fea_blocks_core",
            ),
        ],
        "selectors": [],
    },
    {
        "id": "T3-03",
        "fault": "invalid_core_input",
        "exact": [
            (
                "tests/test_core_regression.py",
                "test_03_invalid_input",
            ),
            (
                "tests/test_assurance_report.py",
                "test_invalid_pipeline_input_is_preserved",
            ),
            (
                "validation/fault_injection_03/prototype/"
                "test_official_fault_injection_probes.py",
                "test_t3_03_invalid_input_blocks_core",
            ),
        ],
        "selectors": [],
    },
    {
        "id": "T3-04",
        "fault": "missing_feasible_domain_evidence",
        "exact": [
            (
                "tests/test_assurance_readiness.py",
                "test_02_missing_evidence_not_ready",
            ),
            (
                "validation/fault_injection_03/prototype/"
                "test_official_fault_injection_probes.py",
                "test_t3_04_missing_evidence_blocks_core",
            ),
        ],
        "selectors": [],
    },
    {
        "id": "T3-05",
        "fault": "human_review_incomplete",
        "exact": [
            (
                "tests/test_human_review_gate.py",
                "test_02_unreviewed_blocks_solver",
            ),
            (
                "validation/fault_injection_03/prototype/"
                "test_official_fault_injection_probes.py",
                "test_t3_05_incomplete_review_blocks_core",
            ),
        ],
        "selectors": [],
    },
    {
        "id": "T3-06",
        "fault": "solver_unknown_or_timeout",
        "exact": [
            (
                "tests/test_pipeline_solver_indeterminate.py",
                "test_01_unknown_is_not_no_escape",
            ),
            (
                "tests/test_assurance_solver_indeterminate.py",
                "test_01_unknown_is_reported_as_indeterminate",
            ),
        ],
        "selectors": [],
    },
    {
        "id": "T3-07",
        "fault": "unsafe_patch_interpretation",
        "exact": [
            (
                "tests/test_patch_semantics.py",
                "test_02_report_does_not_claim_practicality",
            ),
        ],
        "selectors": [],
    },
    {
        "id": "T3-08",
        "fault": "conflicting_correction_history",
        "exact": [
            (
                "tests/test_correction_history.py",
                "test_06_conflicting_history_is_not_auto_resolved",
            ),
            (
                "validation/fault_injection_03/prototype/"
                "test_official_fault_injection_probes.py",
                "test_t3_08_conflict_requires_review",
            ),
        ],
        "selectors": [],
    },
]


_MODULE_CACHE = {}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(relative_path):
    relative_path = str(relative_path)

    if relative_path in _MODULE_CACHE:
        return _MODULE_CACHE[relative_path]

    path = ROOT / relative_path

    if not path.exists():
        raise FileNotFoundError(path)

    module_name = (
        "t3_official_"
        + path.stem
        + "_"
        + hashlib.sha1(
            relative_path.encode("utf-8")
        ).hexdigest()[:8]
    )

    spec = importlib.util.spec_from_file_location(
        module_name,
        path,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"Cannot load test module: {relative_path}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)

    _MODULE_CACHE[relative_path] = module
    return module


def test_classes(module):
    classes = []

    for _, obj in inspect.getmembers(
        module,
        inspect.isclass,
    ):
        if (
            issubclass(obj, unittest.TestCase)
            and obj.__module__ == module.__name__
        ):
            classes.append(obj)

    return classes


def find_exact_test(relative_path, method_name):
    module = load_module(relative_path)

    matches = []

    for cls in test_classes(module):
        if hasattr(cls, method_name):
            matches.append(cls)

    if len(matches) != 1:
        raise RuntimeError(
            f"{relative_path}::{method_name}: "
            f"expected exactly 1 TestCase, "
            f"found {len(matches)}"
        )

    cls = matches[0]

    return (
        cls(method_name),
        (
            f"{relative_path}::"
            f"{cls.__name__}.{method_name}"
        ),
    )


def find_tests_by_literals(
    relative_path,
    literals,
):
    module = load_module(relative_path)

    matches = []

    for cls in test_classes(module):
        for method_name, method in inspect.getmembers(
            cls,
            inspect.isfunction,
        ):
            if not method_name.startswith("test_"):
                continue

            try:
                source = inspect.getsource(method)
            except (OSError, TypeError):
                continue

            if all(
                literal in source
                for literal in literals
            ):
                label = (
                    f"{relative_path}::"
                    f"{cls.__name__}.{method_name}"
                )
                matches.append(
                    (
                        cls(method_name),
                        label,
                    )
                )

    if not matches:
        raise RuntimeError(
            f"No tests in {relative_path} "
            f"matched literals {literals}"
        )

    return matches


def resolve_case(case):
    resolved = []

    for relative_path, method_name in case["exact"]:
        resolved.append(
            find_exact_test(
                relative_path,
                method_name,
            )
        )

    for relative_path, literals in case["selectors"]:
        resolved.extend(
            find_tests_by_literals(
                relative_path,
                literals,
            )
        )

    deduped = {}
    for instance, label in resolved:
        deduped[label] = instance

    return [
        (instance, label)
        for label, instance
        in sorted(deduped.items())
    ]


def load_and_verify_reference():
    actual_sha = sha256(REFERENCE_PATH)

    if actual_sha != EXPECTED_REFERENCE_SHA256:
        raise RuntimeError(
            "Frozen reference SHA256 changed.\n"
            f"Expected: {EXPECTED_REFERENCE_SHA256}\n"
            f"Actual:   {actual_sha}"
        )

    reference = json.loads(
        REFERENCE_PATH.read_text(
            encoding="utf-8"
        )
    )

    metadata = reference["reference_metadata"]

    if (
        metadata["status"]
        != "FROZEN_REFERENCE_V1"
    ):
        raise RuntimeError(
            "Reference is not frozen."
        )

    if (
        metadata["reference_input_sha256"]
        != EXPECTED_REFERENCE_INPUT_SHA256
    ):
        raise RuntimeError(
            "Reference-input SHA does not match "
            "the pre-run frozen value."
        )

    if (
        metadata[
            "official_fault_injection_run_before_freeze"
        ]
        is not False
    ):
        raise RuntimeError(
            "Reference claims an official run "
            "occurred before freeze."
        )

    frozen_matrix = {
        item["id"]: item
        for item in reference["test_matrix"]
    }

    planned_ids = {
        case["id"]
        for case in CASE_PLAN
    }

    if set(frozen_matrix) != planned_ids:
        raise RuntimeError(
            "Runner case IDs do not match "
            "the frozen reference matrix."
        )

    for case in CASE_PLAN:
        frozen_fault = (
            frozen_matrix[case["id"]]["fault"]
        )

        if frozen_fault != case["fault"]:
            raise RuntimeError(
                f"{case['id']} fault mismatch: "
                f"{frozen_fault!r} != "
                f"{case['fault']!r}"
            )

    return reference, actual_sha


def verify_plan_only():
    _, reference_sha = (
        load_and_verify_reference()
    )

    print("TEST #3 OFFICIAL RUNNER PLAN CHECK")
    print("==================================")
    print("REFERENCE SHA256:")
    print(reference_sha)
    print()

    total = 0

    for case in CASE_PLAN:
        resolved = resolve_case(case)

        print(
            f"{case['id']} — {case['fault']}"
        )

        for _, label in resolved:
            print("  ", label)
            total += 1

        print()

    print("Resolved assertion tests:", total)
    print("Official fault execution: NO")
    print("PLAN CHECK: PASS")


def tracked_tree_is_clean():
    worktree = subprocess.run(
        [
            "git",
            "diff",
            "--quiet",
        ],
        cwd=ROOT,
    )

    staged = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--quiet",
        ],
        cwd=ROOT,
    )

    return (
        worktree.returncode == 0
        and staged.returncode == 0
    )


def git_head():
    return subprocess.check_output(
        [
            "git",
            "rev-parse",
            "HEAD",
        ],
        cwd=ROOT,
        text=True,
    ).strip()


def run_case(case):
    resolved = resolve_case(case)

    suite = unittest.TestSuite(
        instance
        for instance, _
        in resolved
    )

    stream = io.StringIO()

    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
    )

    result = runner.run(suite)

    return {
        "passed": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "labels": [
            label
            for _, label
            in resolved
        ],
        "details": stream.getvalue(),
    }


def official_run():
    _, reference_sha = (
        load_and_verify_reference()
    )

    if not tracked_tree_is_clean():
        raise RuntimeError(
            "Tracked Git state is not clean. "
            "Official run aborted."
        )

    pre_run_commit = git_head()

    print(
        "TEST #3 — FIRST OFFICIAL "
        "CONTROLLED FAULT INJECTION RUN"
    )
    print(
        "=============================================="
    )
    print("PRE-RUN COMMIT:")
    print(pre_run_commit)
    print()
    print("REFERENCE SHA256:")
    print(reference_sha)
    print()
    print(
        "FROZEN MATRIX:"
    )
    print(
        ", ".join(
            case["id"]
            for case in CASE_PLAN
        )
    )
    print()
    print(
        "===== OFFICIAL FAULT INJECTION START ====="
    )

    passed_count = 0
    results = []

    for case in CASE_PLAN:
        observed = run_case(case)

        case_passed = observed["passed"]

        if case_passed:
            passed_count += 1

        results.append(
            (
                case,
                observed,
            )
        )

        print()
        print(
            f"{case['id']} — {case['fault']}"
        )
        print("-" * 60)

        for label in observed["labels"]:
            print("assertion_test:", label)

        print(
            "tests_run:",
            observed["tests_run"],
        )

        print(
            "result:",
            "PASS" if case_passed else "FAIL",
        )

        if not case_passed:
            print()
            print("FAILURE DETAILS")
            print(observed["details"])

    print()
    print(
        "===== OFFICIAL FAULT INJECTION END ====="
    )
    print()
    print("FINAL FROZEN-REFERENCE COMPARISON")
    print("---------------------------------")
    print("Expected cases: 8")
    print("Observed cases:", len(results))
    print("Passed cases:", passed_count)
    print(
        "RESULT:",
        (
            "PASS"
            if passed_count == len(CASE_PLAN)
            else "FAIL"
        ),
    )

    if passed_count != len(CASE_PLAN):
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--verify-plan",
        action="store_true",
        help=(
            "Resolve the frozen Test #3 plan "
            "without executing TestCase methods."
        ),
    )

    args = parser.parse_args()

    if args.verify_plan:
        verify_plan_only()
        return

    official_run()


if __name__ == "__main__":
    main()
