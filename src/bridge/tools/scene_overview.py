"""scene_overview — the lists that say what is in the scene."""
from ..connection import call_json


def tool(mode: str = "scene", path: str = None, pattern: str = None,
         node_type: str = None, category: str = None, recursive: bool = False) -> str:
    """List what the scene holds. Start here, before you touch a node.

    Use it to find a node path, to see the shape of a network, or to learn
    which node types this Houdini has.

    Do not use it to read one node in detail: node_inspect does that. Do not
    use it to read geometry: geometry_inspect does that.

    mode:
        "scene"        — file, frame range, counts, and the top of the tree.
        "network"      — the children of one network, with their connections.
        "children"     — the children of `path`. recursive=True walks down.
        "search"       — nodes whose name matches `pattern`, under `path`.
                         node_type filters by type name.
        "node_types"   — the node types this Houdini has: `pattern` is a
                         wildcard on the name ("*bend*") or a word of the
                         label, `category` is "Sop", "Object", "Lop",
                         "Driver". Without both, only the categories.
        "errors"       — every node under `path` that has a cook error.
        "materials"    — the materials in `path` (default /mat) and the types.
        "lights"       — the lights on the USD stage of the LOP node `path`.
        "takes"        — the takes, and which take is current.
        "caches"       — file caches under `path` and their state on disk.
        "render_nodes" — the ROP nodes in /out.
        "viewports"    — the panes, and what the scene viewer shows.

    path: a node path such as "/obj" or "/obj/geo1". Each mode says what it
    means for that mode.

    Returns JSON. A path that does not exist comes back as an error, not as an
    empty list.
    """
    return call_json("scene_overview", {
        "mode": mode, "path": path, "pattern": pattern,
        "node_type": node_type, "category": category, "recursive": recursive,
    })
