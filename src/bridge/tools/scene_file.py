"""scene_file — the .hip file on disk."""
import json

from mcp.types import ToolAnnotations

from ..connection import call_json

ANNOTATIONS = ToolAnnotations(destructiveHint=True)

# Порядок в сети проверяется кодом, не только правилом: агент сложил 27 нод
# в одну точку и не сделал ни одного бокса (стандартный тест 03.10.2026).
_LAYOUT_AUDIT = r'''
import json, collections
report = []
for net in [hou.node("/obj"), hou.node("/stage")] + [n for n in hou.node("/").allSubChildren()
            if n.isNetwork() and n.children() and n.type().category().name() in ("Object", "Lop")]:
    if net is None or not net.isEditable() or net.isInsideLockedHDA():
        continue
    kids = [k for k in net.children() if k.type().name() not in ("subinput", "suboutput")]
    if len(kids) < 4:
        continue
    pos = collections.Counter((round(k.position()[0], 1), round(k.position()[1], 1)) for k in kids)
    stacked = sum(c for c in pos.values() if c > 1)
    boxes_needed = net.childTypeCategory().name() in ("Sop", "Lop", "Cop")
    unboxed = [k.name() for k in kids if boxes_needed and not k.parentNetworkBox()]
    if stacked or unboxed:
        report.append({"network": net.path(), "nodes": len(kids), "stacked": stacked,
                       "outside_boxes": len(unboxed), "examples": unboxed[:5]})
print(json.dumps(report))
'''


def _layout_check():
    try:
        out = json.loads(call_json("execute", {"source": _LAYOUT_AUDIT, "mode": "python",
                                               "timeout": 30}, timeout=60.0))
        text = out.get("stdout") or out.get("output") or ""
        return json.loads(text.strip().splitlines()[-1]) if text.strip() else []
    except Exception as error:  # проверка не должна ломать сохранение
        return [{"error": str(error)}]


def tool(mode: str = "info", path: str = None) -> str:
    """Read, save or load the scene file.

    Use "save" before a change that is hard to undo, and use "info" to learn
    whether the session holds work that is not saved.

    mode:
        "info" — the file name, the frame range, the counts, and whether the
                 session has changes that are not saved.
        "save" — save to `path`, or over the open file when `path` is empty.
                 The answer has `layout_check`: networks with nodes stacked on
                 one spot or left outside network boxes. Fix every entry
                 before you call the work done (lay out, box, name).
        "load" — open the .hip file at `path`. Everything in the session goes
                 away, and the undo history with it.

    Returns JSON.
    """
    result = call_json("scene_file", {"mode": mode, "path": path}, timeout=300.0)
    if mode != "save":
        return result
    data = json.loads(result)
    data["layout_check"] = _layout_check()
    return json.dumps(data)
