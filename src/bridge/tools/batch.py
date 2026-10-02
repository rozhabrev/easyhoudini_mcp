"""batch — several tool calls in one round trip and one undo group."""
import json
from typing import Any, Dict, List

from mcp.server.mcpserver import Image
from mcp.server.mcpserver.exceptions import ToolError

from ..connection import call, session_line
from .capture import pictures as pictures_of


def tool(operations: List[Dict[str, Any]]) -> list[Image | str]:
    """Run several Houdini tools in one call.

    Use it to build a network: many nodes, their wires and their parameters go
    in one round trip and one undo group, and a person can undo the whole thing
    with one keystroke.

    Do not use it when a later step needs to read what an earlier step made.
    The list runs without you in the middle, so nothing can branch on a result.

    operations: a list. Each item is {"tool": "<tool name>", "params": {...}},
    with the same parameters that the tool takes on its own. Every tool in this
    server can go in the list, except batch itself.

    Every step is checked before any step runs: a step with a wrong argument
    stops the batch with its index and its error, and nothing changes.

    Returns JSON with one result for each operation, and the picture of every
    capture step. The list stops at the first failure, because a later step
    usually needs the node that an earlier step made: the report names the
    index that failed and the error, and the steps before it stay.

    A capture step with no `output` writes to a file of its own, so one batch
    can hold several captures.
    """
    from . import validate

    steps = []
    for index, operation in enumerate(operations):
        name = operation.get("tool") or operation.get("type")
        params = {key: value for key, value in (operation.get("params") or {}).items()
                  if value is not None}
        if name == "batch":
            raise ToolError(f"Step {index}: batch cannot hold batch.")
        try:
            validate(name, params)
        except Exception as error:
            raise ToolError(f"Step {index} ({name}) was refused, and no step ran: "
                            f"{error}") from error
        steps.append({"tool": name, "params": params})

    report = call("batch", {"operations": steps}, timeout=600.0)
    pictures = []
    for step in report.get("results", []):
        result = step.get("result")
        if step.get("tool") != "capture" or not isinstance(result, dict):
            continue
        pictures.extend(pictures_of(result))
    report["_session"] = session_line()
    return pictures + [json.dumps(report, indent=2, default=str)]
