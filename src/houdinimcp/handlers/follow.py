"""The panes follow the work of the agent.

The agent works through code, and Houdini does not move a pane for that: the
network editor stays where the person left it and the viewer keeps drawing
the old display node. A timelapse of such a session is the same empty frame a
hundred times. So before each timelapse frame the panes go to the node that
the last call changed, and the viewer draws the end of the chain the agent
grows.
"""
import contextlib
import re

import hou

# A node path in the source of an execute call, as in hou.node("/stage/box1").
_PATH_IN_CODE = re.compile(r"""["'](/(?:obj|stage|mat|out|img|ch|tasks)(?:/[\w.-]+)+)["']""")


def nodes_now():
    """The session id of every node outside locked assets. execute names no
    node in its params, so the nodes it made are the ones that are new."""
    with contextlib.suppress(Exception):
        return {node.sessionId() for node in
                hou.node("/").allSubChildren(recurse_in_locked_nodes=False)}
    return None


def _as_node(value):
    if not isinstance(value, str) or not value.startswith("/"):
        return None
    node = hou.node(value)
    if node is None:
        parm = hou.parm(value)
        node = parm.node() if parm is not None else None
    return node


def _walk(value, found, depth=0):
    """Every node path in a JSON value, in order."""
    if depth > 6 or len(found) > 200:
        return
    if isinstance(value, str):
        node = _as_node(value)
        if node is not None:
            found.append(node)
    elif isinstance(value, dict):
        for item in value.values():
            _walk(item, found, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _walk(item, found, depth + 1)


# The session id of every node that the agent made in this session. The
# display flag moves only away from such a node: the display node of the user
# decides what a network outputs (what a SOP Create gives the stage), and a
# flag moved off it changed the scene and started a heavy cook (09.10.2026).
MADE = set()


def touched(command, params, result=None, before=None):
    """The node that a call worked on last, or None."""
    found = []
    if command == "select" and params.get("paths"):
        # The node to show is the one asked for. The result also names its
        # network, and following that showed the network one level up.
        paths = params["paths"] if isinstance(params["paths"], list) else [params["paths"]]
        node = _as_node(paths[0])
        if node is not None:
            return node
    if before is not None:
        new = [node for node in hou.node("/").allSubChildren(recurse_in_locked_nodes=False)
               if node.sessionId() not in before]
        MADE.update(node.sessionId() for node in new)
        # The last new node that is not inside a new node: the top of what
        # the call made, not the inside of an asset it made.
        tops = [node for node in new if node.parent() is None
                or node.parent().sessionId() in before]
        found.extend(tops or new)
    if not found and command == "execute":
        for path in _PATH_IN_CODE.findall(str(params.get("source") or "")):
            node = _as_node(path)
            if node is not None:
                found.append(node)
    if not found:
        _walk(result, found)
    if not found:
        _walk(params, found)
    return found[-1] if found else None


def _workable(node):
    """The node itself, or None when it has gone or is not in a network."""
    with contextlib.suppress(hou.ObjectWasDeleted, AttributeError):
        if node is not None and node.parent() is not None:
            return node
    return None


# Nodes that can cook for minutes or quit Houdini when the viewer cooks them
# with the parameters they have at creation. The display flag goes to them
# only when the agent puts it there.
HEAVY = re.compile(r"fracture|solver|dopnet|dopimport|sim|vellum|pyro|flip|"
                   r"rbd|mpm|cache|ocean|crowd|karma|render", re.IGNORECASE)


def heavy(node):
    with contextlib.suppress(Exception):
        return bool(HEAVY.search(node.type().name()))
    return False


def advance_display(node):
    """Put the display flag on `node` when it is the new end of the chain that
    the viewer draws: it has no outputs, and the node that holds the flag now
    feeds it. A side branch or a node in another chain keeps the flag where
    it is, and so does a flag on a node that the agent did not make: the
    flag moves only inside the network of the work. Returns the node that got
    the flag, or None."""
    if not isinstance(node, (hou.SopNode, hou.LopNode)) or heavy(node):
        return None
    if node.outputs() or node.isDisplayFlagSet():
        return None
    current = None
    with contextlib.suppress(AttributeError, hou.Error):
        current = node.parent().displayNode()
    if current is not None and current not in node.inputAncestors():
        return None
    if current is not None and current.sessionId() not in MADE:
        return None
    with contextlib.suppress(hou.Error):
        node.setDisplayFlag(True)
        return node
    return None


def stage_box(lop):
    """The world box of the USD stage of a LOP node, cameras and lights out."""
    from pxr import Usd, UsdGeom
    stage = lop.stage() if lop is not None else None
    if stage is None:
        return None
    cache = UsdGeom.BBoxCache(Usd.TimeCode(hou.frame()), [UsdGeom.Tokens.default_,
                                                          UsdGeom.Tokens.render])
    extent = cache.ComputeWorldBound(stage.GetPseudoRoot()).ComputeAlignedRange()
    if extent.IsEmpty():
        return None
    low, high = extent.GetMin(), extent.GetMax()
    return hou.BoundingBox(low[0], low[1], low[2], high[0], high[1], high[2])


def network_box(network):
    """The box of what the viewer draws in `network`: the display SOP of a
    SOP network, the stage of a LOP network, the displayed objects of /obj."""
    with contextlib.suppress(Exception):
        if network.path() == "/obj":
            # An empty hou.BoundingBox() is a point at the origin, not
            # nothing: start from the first real box.
            box = None
            for child in network.children():
                if child.type().name() == "geo" and child.isObjectDisplayed() \
                        and child.displayNode() is not None:
                    part = child.displayNode().geometry().boundingBox()
                    if part.isValid():
                        part = part * child.worldTransform()
                        if box is None:
                            box = part
                        else:
                            box.enlargeToContain(part)
            return box
        shown = network.displayNode()
        if isinstance(shown, hou.LopNode):
            return stage_box(shown)
        if isinstance(shown, hou.SopNode):
            box = shown.geometry().boundingBox()
            return box if box.isValid() else None
    return None


def outgrown(box, framed):
    """True when the view must frame `box` again: it leaves the framed box,
    or it is much smaller, so that the work is a dot in the picture."""
    if box is None:
        return False
    if framed is None:
        return True
    grow = framed.sizevec() * 0.05
    inside = all(box.minvec()[i] >= framed.minvec()[i] - grow[i]
                 and box.maxvec()[i] <= framed.maxvec()[i] + grow[i] for i in range(3))
    return not inside or box.sizevec().length() < 0.35 * framed.sizevec().length()


def grown(box, fill=0.85):
    """The box with room around it, so the work does not touch the edges."""
    pad = box.sizevec() * ((1.0 / fill - 1.0) * 0.5)
    return hou.BoundingBox(*(box.minvec() - pad), *(box.maxvec() + pad))


# The box that the viewer of each network framed last.
FRAMED = {}


def _frame_network(editor, node):
    """Frame all the nodes of the network when `node` is out of view."""
    with contextlib.suppress(Exception):
        bounds = editor.visibleBounds()
        if bounds.contains(node.position()):
            return
        items = node.parent().children()
        rect = hou.BoundingRect(node.position(), node.position() + node.size())
        for item in items:
            rect.enlargeToContain(item.position())
            rect.enlargeToContain(item.position() + item.size())
        rect.expand((2.0, 2.0))
        editor.setVisibleBounds(rect)


def panes(node):
    """Turn the network editor and the viewer to `node`."""
    shown = {"node": node.path(), "display": None}
    editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    if editor is not None:
        with contextlib.suppress(Exception):
            if editor.pwd() != node.parent():
                editor.setPwd(node.parent())
            node.setSelected(True, clear_all_selected=True)
            _frame_network(editor, node)
    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    network = None
    if isinstance(node, hou.ObjNode):
        network = hou.node("/obj")
    elif isinstance(node, (hou.SopNode, hou.LopNode)):
        network = node.parent()
    if viewer is not None and network is not None:
        with contextlib.suppress(Exception):
            if viewer.pwd() != network:
                viewer.setPwd(network)
                FRAMED.pop(network.path(), None)
            box = network_box(network)
            if outgrown(box, FRAMED.get(network.path())):
                viewer.curViewport().frameBoundingBox(grown(box))
                FRAMED[network.path()] = box
            shown["viewer"] = network.path()
    return shown


def follow(node):
    """Advance the display flag and turn the panes to `node`. Never raises:
    a pane that cannot follow must not fail the call of the agent."""
    node = _workable(node)
    if node is None or not hou.isUIAvailable():
        return None
    try:
        displayed = advance_display(node)
        shown = panes(node)
        shown["display"] = displayed.path() if displayed is not None else None
        return shown
    except Exception as error:  # a pane, a deleted node: keep the call alive
        return {"node": node.path(), "error": f"{type(error).__name__}: {error}"}
