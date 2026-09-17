"""Normalize one LangSmith CLI trace-export JSONL file into an ABL Workflow.

This adapter records observed runs. It does not make assurance judgments or infer
that retrieved documents support the trace's final output.
"""

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agent_boundary_lab.assurance.models import Workflow
from agent_boundary_lab.assurance.schema import WorkflowValidationError, parse_workflow

MAX_INPUT_BYTES = 16 * 1024 * 1024
MAX_LINE_BYTES = 1024 * 1024
MAX_RUNS = 1000  # The inspected LangSmith CLI export queries at most 1000 runs.
MAX_JSON_DEPTH = 32
_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_SENSITIVE_RE = re.compile(
    r"(?i)authorization|bearer|api[_-]?key|access[_-]?token|secret|password"
)


class LangSmithImportError(ValueError):
    """The export cannot be normalized without inventing or losing structure."""


@dataclass(frozen=True)
class _Run:
    run_id: str
    trace_id: str
    parent_run_id: str | None
    name: str | None
    run_type: str | None
    start_time: str | None
    start_instant: datetime | None
    end_time: str | None
    status: str | None
    duration_ms: float | None
    error: str | None
    inputs: dict[str, Any] | None
    outputs: dict[str, Any] | None


def _optional_text(value: Any, field: str, line: int) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise LangSmithImportError(f"line {line}: {field} must be a string or null")
    return value if value.strip() else None


def _required_id(value: Any, field: str, line: int) -> str:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        raise LangSmithImportError(
            f"line {line}: {field} must be a nonempty identifier of at most 128 safe characters"
        )
    return value


def _timestamp(value: Any, field: str, line: int) -> tuple[str | None, datetime | None]:
    text = _optional_text(value, field, line)
    if text is None:
        return None, None
    try:
        instant = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise LangSmithImportError(f"line {line}: invalid {field}: {error}") from error
    if instant.tzinfo is None:
        raise LangSmithImportError(f"line {line}: {field} must include a timezone")
    return text, instant.astimezone(timezone.utc)


def _optional_object(value: Any, field: str, line: int) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or not all(isinstance(k, str) for k in value):
        raise LangSmithImportError(f"line {line}: {field} must be an object or null")
    return value


def _check_depth(value: Any, line: int) -> None:
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > MAX_JSON_DEPTH:
            raise LangSmithImportError(
                f"line {line}: JSON nesting exceeds {MAX_JSON_DEPTH} levels"
            )
        if isinstance(item, dict):
            pending.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            pending.extend((child, depth + 1) for child in item)


def _parse_run(value: Any, line: int) -> _Run:
    if not isinstance(value, dict):
        raise LangSmithImportError(f"line {line}: expected one run object")
    run_id = _required_id(value.get("run_id"), "run_id", line)
    trace_id = _required_id(value.get("trace_id"), "trace_id", line)
    parent_value = value.get("parent_run_id")
    parent_run_id = (
        None
        if parent_value is None
        else _required_id(parent_value, "parent_run_id", line)
    )
    start_time, start_instant = _timestamp(value.get("start_time"), "start_time", line)
    end_time, _ = _timestamp(value.get("end_time"), "end_time", line)
    duration_value = value.get("duration_ms")
    duration_ms: float | None = None
    if duration_value is not None:
        if (
            isinstance(duration_value, bool)
            or not isinstance(duration_value, (int, float))
            or not math.isfinite(duration_value)
            or duration_value < 0
        ):
            raise LangSmithImportError(
                f"line {line}: duration_ms must be a nonnegative finite number or null"
            )
        duration_ms = float(duration_value)
    inputs = _optional_object(value.get("inputs"), "inputs", line)
    outputs = _optional_object(value.get("outputs"), "outputs", line)
    for item in (inputs, outputs):
        if item is not None:
            _check_depth(item, line)
    return _Run(
        run_id=run_id,
        trace_id=trace_id,
        parent_run_id=parent_run_id,
        name=_optional_text(value.get("name"), "name", line),
        run_type=_optional_text(value.get("run_type"), "run_type", line),
        start_time=start_time,
        start_instant=start_instant,
        end_time=end_time,
        status=_optional_text(value.get("status"), "status", line),
        duration_ms=duration_ms,
        error=_optional_text(value.get("error"), "error", line),
        inputs=inputs,
        outputs=outputs,
    )


def _safe_text(value: str | None, limit: int) -> str | None:
    if value is None or len(value) > limit or _SENSITIVE_RE.search(value):
        return None
    if any(ord(char) < 32 or ord(char) == 127 for char in value):
        return None
    if "://" in value and "?" in value:
        return None
    return value


def _safe_locator(value: Any) -> str | None:
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or any(ord(char) <= 32 or ord(char) == 127 for char in value)
    ):
        return None
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or _SENSITIVE_RE.search(value)
        ):
            return None
    except ValueError:
        return None
    return value


def _document_list(run: _Run) -> tuple[str, list[Any]] | None:
    if run.run_type != "retriever" or run.outputs is None:
        return None
    for key in ("documents", "output"):
        documents = run.outputs.get(key)
        if isinstance(documents, list):
            return key, documents
    return None


def _event(run: _Run, sequence: int) -> dict[str, Any]:
    event: dict[str, Any] = {"event_id": run.run_id, "sequence": sequence}
    if run.parent_run_id is not None:
        event["parent_event_id"] = run.parent_run_id
    run_type = _safe_text(run.run_type, 64)
    if run_type is not None:
        event["event_type"] = run_type
        event["metadata"] = {"langsmith_run_type": run_type}
    name = _safe_text(run.name, 256)
    if name is not None:
        event["action"] = name
        if run.run_type == "tool":
            event["tool"] = name
    if run.status in {"success", "error"} and run.end_time is not None:
        event["executed"] = True
    if run.start_time is not None:
        event["timestamp"] = run.start_time
    if run.duration_ms is not None:
        event["latency_ms"] = run.duration_ms
    error = _safe_text(run.error, 512)
    if error is not None:
        event["error"] = error
    elif run.error is not None:
        event["error"] = "LangSmith error recorded; details omitted"
    if run.inputs is not None:
        query = _safe_text(
            run.inputs.get("query")
            if isinstance(run.inputs.get("query"), str)
            else None,
            512,
        )
        if query is not None:
            event["query"] = query
    status = _safe_text(run.status, 64)
    summary = f"status={status}" if status is not None else "status=unknown"
    documents = _document_list(run)
    if documents is not None:
        key, items = documents
        summary += f"; {len(items)} document in outputs.{key}"
    elif run.outputs:
        summary += "; output field present"
    elif run.error is not None:
        summary += "; error recorded"
    event["observation"] = summary
    return event


def _has_final_output(run: _Run) -> bool:
    if (
        run.status not in (None, "success")
        or run.end_time is None
        or run.error is not None
    ):
        return False
    if run.outputs is None:
        return False
    return any(value not in (None, "", [], {}) for value in run.outputs.values())


class LangSmithTraceAdapter:
    """Read an official CLI-normalized single-trace JSONL export."""

    def import_file(self, path: Path) -> Workflow:
        try:
            size = path.stat().st_size
        except OSError as error:
            raise LangSmithImportError(f"{path}: cannot read input: {error}") from error
        if not path.is_file():
            raise LangSmithImportError(f"{path}: expected a regular JSONL file")
        if size > MAX_INPUT_BYTES:
            raise LangSmithImportError(
                f"{path}: input exceeds {MAX_INPUT_BYTES} byte limit"
            )
        runs: list[_Run] = []
        try:
            with path.open("r", encoding="utf-8-sig") as stream:
                for line_number, line in enumerate(stream, start=1):
                    if len(line.encode("utf-8")) > MAX_LINE_BYTES:
                        raise LangSmithImportError(
                            f"{path}: line {line_number} exceeds {MAX_LINE_BYTES} bytes"
                        )
                    if not line.strip():
                        raise LangSmithImportError(
                            f"{path}: line {line_number} is blank"
                        )
                    try:
                        value = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise LangSmithImportError(
                            f"{path}: line {line_number}: invalid JSON: {error.msg}"
                        ) from error
                    try:
                        runs.append(_parse_run(value, line_number))
                    except LangSmithImportError as error:
                        raise LangSmithImportError(f"{path}: {error}") from error
                    if len(runs) >= MAX_RUNS:
                        raise LangSmithImportError(
                            f"{path}: {MAX_RUNS} runs may be a truncated CLI export"
                        )
        except (OSError, UnicodeError) as error:
            raise LangSmithImportError(f"{path}: cannot read JSONL: {error}") from error
        return self.normalize(runs, path)

    def normalize(self, runs: list[_Run], path: Path) -> Workflow:
        if not runs:
            raise LangSmithImportError(f"{path}: empty JSONL export")
        trace_ids = {run.trace_id for run in runs}
        if len(trace_ids) != 1:
            raise LangSmithImportError(f"{path}: mixed trace_id values")
        run_ids = [run.run_id for run in runs]
        if len(set(run_ids)) != len(run_ids):
            raise LangSmithImportError(f"{path}: duplicate run_id")
        roots = [run for run in runs if run.parent_run_id is None]
        if len(roots) != 1 or roots[0].run_id != runs[0].trace_id:
            raise LangSmithImportError(
                f"{path}: expected exactly one root with run_id=trace_id"
            )
        root = roots[0]
        for run in runs:
            if run.parent_run_id is not None and run.parent_run_id not in run_ids:
                raise LangSmithImportError(
                    f"{path}: run {run.run_id} has dangling parent_run_id "
                    f"{run.parent_run_id}"
                )
        ordered = sorted(
            runs,
            key=lambda run: (
                run.start_instant or datetime.max.replace(tzinfo=timezone.utc),
                run.run_id,
            ),
        )
        events = [_event(run, index) for index, run in enumerate(ordered)]
        sources: list[dict[str, Any]] = []
        source_by_id: dict[str, dict[str, Any]] = {}
        artifacts: list[dict[str, Any]] = []
        for run in ordered:
            document_output = _document_list(run)
            if document_output is None:
                continue
            _, documents = document_output
            source_refs: list[str] = []
            for index, document in enumerate(documents):
                if not isinstance(document, dict) or document.get("type") != "Document":
                    continue
                metadata = document.get("metadata")
                if not isinstance(metadata, dict):
                    continue
                doc_id_value = metadata.get("doc_id")
                doc_id = (
                    doc_id_value
                    if isinstance(doc_id_value, str) and _ID_RE.fullmatch(doc_id_value)
                    else None
                )
                locator = _safe_locator(
                    metadata.get("source")
                    or metadata.get("url")
                    or metadata.get("locator")
                )
                if doc_id is None and locator is None:
                    continue
                source_id = doc_id or f"langsmith:{run.run_id}:document:{index}"
                source: dict[str, Any] = {
                    "source_id": source_id,
                    "source_type": "retrieved_document",
                }
                if locator is not None:
                    source["locator"] = locator
                title = _safe_text(
                    metadata.get("title")
                    if isinstance(metadata.get("title"), str)
                    else None,
                    256,
                )
                if title is not None:
                    source["title"] = title
                if doc_id is not None:
                    source["metadata"] = {"langsmith_document_id": doc_id}
                previous = source_by_id.get(source_id)
                if previous is not None and previous != source:
                    raise LangSmithImportError(
                        f"{path}: conflicting document identity {source_id}"
                    )
                if previous is None:
                    source_by_id[source_id] = source
                    sources.append(source)
                if source_id not in source_refs:
                    source_refs.append(source_id)
            artifacts.append(
                {
                    "artifact_id": f"retrieval:{run.run_id}",
                    "artifact_type": "retrieval_result",
                    "artifact_role": "INTERMEDIATE",
                    "produced_by_event": run.run_id,
                    "source_refs": source_refs,
                }
            )
        if _has_final_output(root):
            artifacts.append(
                {
                    "artifact_id": f"output:{root.run_id}",
                    "artifact_type": "trace_root_output",
                    "artifact_role": "FINAL_OUTPUT",
                    "produced_by_event": root.run_id,
                }
            )
        workflow: dict[str, Any] = {
            "workflow_id": f"langsmith:{root.trace_id}",
            "events": events,
            "sources": sources,
            "evidence": [],
            "claims": [],
            "artifacts": artifacts,
            "assurance_context": {"events": []},
        }
        title = _safe_text(root.name, 256)
        if title is not None:
            workflow["title"] = title
        try:
            return parse_workflow(workflow)
        except WorkflowValidationError as error:
            raise LangSmithImportError(
                f"{path}: normalized workflow is invalid: {error}"
            ) from error
