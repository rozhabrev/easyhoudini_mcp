"""Scene context and introspection handlers."""
import hou


def get_network_overview(path="/obj"):
    """Get an overview of all nodes in a network with their connections."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    children = node.children()
    nodes = []
    for child in children:
        info = {
            "name": child.name(),
            "path": child.path(),
            "type": child.type().name(),
            "inputs": [inp.path() for inp in child.inputs() if inp],
            "outputs": [conn.outputNode().path() for conn in child.outputConnections()],
        }
        nodes.append(info)
    return {"path": path, "node_count": len(nodes), "nodes": nodes}


def get_cook_chain(path):
    """Get the cook dependency chain for a node (inputs all the way up)."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    chain = []
    visited = set()

    def _walk(n):
        if n.path() in visited:
            return
        visited.add(n.path())
        for inp in n.inputs():
            if inp:
                _walk(inp)
        chain.append({
            "name": n.name(),
            "path": n.path(),
            "type": n.type().name(),
        })

    _walk(node)
    return {"path": path, "chain": chain}


def explain_node(path):
    """Get a human-readable explanation of a node: type, parms, connections."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    node_type = node.type()
    parms = []
    for parm in node.parms():
        if parm.isAtDefault():
            continue
        parms.append({
            "name": parm.name(),
            "label": parm.parmTemplate().label(),
            "value": str(parm.eval()),
        })
    inputs = []
    for i, inp in enumerate(node.inputs()):
        if inp:
            inputs.append({"index": i, "path": inp.path(), "type": inp.type().name()})
    outputs = []
    for conn in node.outputConnections():
        out = conn.outputNode()
        outputs.append({"path": out.path(), "type": out.type().name(), "input_index": conn.inputIndex()})
    return {
        "path": node.path(),
        "type": node_type.name(),
        "label": node_type.description(),
        "category": node_type.category().name(),
        "non_default_parms": parms,
        "inputs": inputs,
        "outputs": outputs,
        "comment": node.comment(),
    }


def get_scene_summary():
    """Get a high-level summary of the entire scene."""
    root = hou.node("/")
    all_nodes = root.allSubChildren()
    type_counts = {}
    for n in all_nodes:
        cat = n.type().category().name()
        type_counts[cat] = type_counts.get(cat, 0) + 1
    hip_file = hou.hipFile.name()
    return {
        "file": hip_file,
        "total_nodes": len(all_nodes),
        "category_counts": type_counts,
        "fps": hou.fps(),
        "frame_range": list(hou.playbar.frameRange()),
        "current_frame": hou.intFrame(),
    }


def get_selection():
    """Get the currently selected nodes."""
    selected = hou.selectedNodes()
    nodes = []
    for n in selected:
        nodes.append({
            "name": n.name(),
            "path": n.path(),
            "type": n.type().name(),
        })
    return {"count": len(nodes), "nodes": nodes}


def set_selection(paths):
    """Set the node selection to the given list of paths."""
    nodes = []
    for p in paths:
        n = hou.node(p)
        if not n:
            raise ValueError(f"Node not found: {p}")
        nodes.append(n)
    # Clear current selection
    for n in hou.selectedNodes():
        n.setSelected(False)
    for n in nodes:
        n.setSelected(True)
    return {"selected": [n.path() for n in nodes]}


def show(paths, display=False):
    """Put the work in front of the person: the network editor opens the
    network of the first node and frames the nodes, the scene viewer shows that
    network and frames what it draws. The agent works through code, and the
    panes never follow it on their own: without this a screen recording shows
    an empty network and an old picture for the whole session.

    display: also move the display flag to the first node, so the viewer draws
    its result. Off by default, because it changes what the scene outputs.
    """
    set_selection(paths)
    node = hou.node(paths[0])
    shown = {"network": node.parent().path(), "display": None, "viewer": None}
    if display and hasattr(node, "setDisplayFlag"):
        node.setDisplayFlag(True)
        shown["display"] = node.path()
    if not hou.isUIAvailable():
        shown["note"] = "No Houdini window: nothing to show."
        return shown
    editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    if editor:
        editor.setCurrentNode(node)
        try:
            editor.homeToSelection()
        except (AttributeError, hou.Error):
            pass
    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    if viewer:
        try:
            viewer.setPwd(node.parent())
            port = viewer.curViewport()
            if isinstance(node, hou.LopNode):
                port.frameAll()
            else:
                port.frameSelected()
            shown["viewer"] = viewer.pwd().path()
        except hou.Error as error:
            shown["note"] = f"The viewer could not show it: {error}"
    return shown
