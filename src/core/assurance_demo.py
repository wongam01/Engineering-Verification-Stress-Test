from src.core.json_io import (
    load_engineering_case,
)

from src.core.pipeline import (
    run_pipeline,
)

from src.core.assurance_report import (
    build_assurance_report,
    render_assurance_report,
)


# =========================================================
# HEATING SKID DEMO
# =========================================================

def run_heating_skid_demo():
    """
    실제 Heating Skid Engineering Case를

    JSON
    → Core Pipeline
    → Z3 Stress Test
    → Patch Evaluation
    → Assurance Report

    순서로 실행한다.
    """

    case = load_engineering_case(
        "samples/heating_skid_case.json"
    )

    pipeline_result = run_pipeline(
        case,
        generate_patches=True,
    )

    report = build_assurance_report(
        case_name=case.name,
        pipeline_result=pipeline_result,
    )

    print()
    print(
        render_assurance_report(
            report
        )
    )
    print()


# =========================================================
# MAIN
# =========================================================

def main():
    run_heating_skid_demo()


if __name__ == "__main__":
    main()