"""scene_file — the .hip file on disk."""
import json

from mcp.types import ToolAnnotations

from .. import structure
from ..connection import call_json

ANNOTATIONS = ToolAnnotations(destructiveHint=True)

# The network order is checked in code, not only by a rule: in a test run an
# agent stacked 27 nodes on one spot and made no network box at all, and in
# 0.4 runs it left empty and repeated boxes and subnets (see bridge.structure).
def _layout_check():
    return structure.audit(layout=True)


def tool(mode: str = "info", path: str = None) -> str:
    """Read, save or load the scene file.

    Use "save" before a change that is hard to undo, and use "info" to learn
    whether the session holds work that is not saved.

    mode:
        "info" — the file name, the frame range, the counts, and whether the
                 session has changes that are not saved.
        "save" — save to `path`, or over the open file when `path` is empty.
                 The answer has `layout_check`: networks with nodes stacked on
                 one spot, drawn over each other or left outside network boxes,
                 boxes over each other, empty boxes, two
                 boxes with one title, subnets that repeat or hold nothing,
                 nodes left wired to nothing, boxes spread far wider than
                 their nodes.
                 Fix every entry before you call the work done (lay out, put
                 into the box that is there, delete the empty and the
                 repeated ones).
        "load" — open the .hip file at `path`. Everything in the session goes
                 away, and the undo history with it.

    Returns JSON.
    """
    result = call_json("scene_file", {"mode": mode, "path": path}, timeout=300.0)
    if mode != "save":
        return result
    data = json.loads(result)
    data["layout_check"] = _layout_check()
    if data["layout_check"]:
        # A run read the report as a note about old work and answered with the
        # new nodes still outside their box (11.10.2026).
        data["layout_check_todo"] = (
            "Fix every entry now, before you answer, and save again. Each entry is "
            "nodes that you made (the ai prefix, OUT_), in this request or an earlier "
            "one; the user's nodes are never listed. Put a node into the box of its "
            "block, move overlapping nodes apart, fit a spread box around its nodes, "
            "delete empty or repeated boxes and subnets and nodes wired to nothing. "
            "Only when an entry is work the user asked you to keep, say so.")
    return json.dumps(data)
