"""Command-line interface for Agent Boundary Lab."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from agent_boundary_lab.assurance.models import OverallStatus
from agent_boundary_lab.assurance.schema import WorkflowValidationError, load_workflow
from agent_boundary_lab.assurance.verifier import verify_workflow

DEFAULT_REPORT_PATH = Path("artifacts/assurance_report.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="abl")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser(
        "verify", help="verify a research-workflow JSON document"
    )
    verify.add_argument("workflow", type=Path)
    verify.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help=f"report path (default: {DEFAULT_REPORT_PATH.as_posix()})",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _parser().parse_args(argv)
    if args.command != "verify":
        return 2
    try:
        workflow = load_workflow(args.workflow)
    except WorkflowValidationError as error:
        print(f"WORKFLOW_VALIDATION_ERROR: {error}", file=sys.stderr)
        return 2

    report = verify_workflow(workflow)
    output: Path = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"workflow_id={report.workflow_id}")
    print(f"status={report.summary.overall_status.value}")
    print(f"findings={report.summary.total_findings}")
    print(f"report={output}")
    return 0 if report.summary.overall_status is OverallStatus.COMPLETE else 1


if __name__ == "__main__":
    raise SystemExit(main())
