"""Command-line interface for Agent Boundary Lab."""

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from agent_boundary_lab.assurance.models import ArtifactRole, OverallStatus
from agent_boundary_lab.assurance.schema import WorkflowValidationError, load_workflow
from agent_boundary_lab.assurance.verifier import verify_workflow
from agent_boundary_lab.langsmith_adapter import (
    LangSmithImportError,
    LangSmithTraceAdapter,
)

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
    importer = subparsers.add_parser(
        "import", help="normalize an external trace into a workflow"
    )
    formats = importer.add_subparsers(dest="import_format", required=True)
    langsmith = formats.add_parser(
        "langsmith", help="import one LangSmith CLI trace-export JSONL file"
    )
    langsmith.add_argument("input", type=Path)
    langsmith.add_argument("--output", type=Path, required=True)
    return parser


def _import_langsmith(input_path: Path, output: Path) -> int:
    try:
        workflow = LangSmithTraceAdapter().import_file(input_path)
    except LangSmithImportError as error:
        print(f"LANGSMITH_IMPORT_ERROR: {error}", file=sys.stderr)
        return 2

    created = False
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            stream.write(
                json.dumps(
                    asdict(workflow), indent=2, sort_keys=True, ensure_ascii=False
                )
                + "\n"
            )
    except OSError as error:
        if created:
            output.unlink(missing_ok=True)
        print(
            f"LANGSMITH_IMPORT_ERROR: {input_path}: cannot write {output}: {error}",
            file=sys.stderr,
        )
        return 2

    final_output = any(
        artifact.artifact_role is ArtifactRole.FINAL_OUTPUT
        for artifact in workflow.artifacts
    )
    print(f"workflow_id={workflow.workflow_id}")
    print(f"events={len(workflow.events)}")
    print(f"candidate_sources={len(workflow.sources)}")
    print(f"final_output_identified={str(final_output).lower()}")
    print("provenance_governance_approval=unknown")
    print(f"workflow={output}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = _parser().parse_args(argv)
    if args.command == "import":
        if args.import_format == "langsmith":
            return _import_langsmith(args.input, args.output)
        return 2
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
