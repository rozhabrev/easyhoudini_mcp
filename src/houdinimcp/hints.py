"""What to do about the errors that agents make again and again.

Each entry here comes from the error log of real runs (`houdinimcp-bridge
errors`): the same few mistakes made most of the failed calls. A bare Python
error says what broke, not what to do, so the agent guessed and got it again.
A hint names the fix: the path that is not there and the ones that are, the
node type that does not exist and the ones that do, the locked asset that
refused the write.

A hint is a help, never a second failure: every lookup here is guarded.
"""
import difflib
import re

import hou

# A wrong guess at the API of one kind of node, and the call that exists.
API = {
    ("RopNode", "setDisplayFlag"): "A ROP node has no display flag. It renders with "
        "node.render() or the render tool; to switch it off use node.bypass(True).",
    ("LopNode", "geometry"): "A LOP node makes a USD stage, not geometry. Read it with "
        "node.stage() or the stage_inspect tool. For the geometry of a SOP Create, read "
        "the SOP node inside it (hou.node('<sop create>/sopnet/create/<node>').geometry()).",
    ("CopNode", "planes"): "A Copernicus COP has layers, not planes: node.layer(index) "
        "gives a hou.ImageLayer (bufferResolution(), channelCount()), and "
        "node.outputLabels() names the outputs. planes() belongs to the old COP2 nodes.",
    ("CopNode", "xRes"): "A Copernicus COP has no xRes: read "
        "node.layer().bufferResolution().",
    (None, "inputLabel"): "There is no inputLabel(index). Use node.inputLabels(), a tuple, "
        "and index it: node.inputLabels()[0]. node.outputLabels() works the same way.",
}


def hint(message: str, code: str = None) -> str:
    """A short text that says how to fix this error, or an empty text."""
    try:
        return _hint(message or "", code or "")
    except Exception:
        return ""


def _hint(message, code):
    found = re.search(r"'(\w+)' object has no attribute '(\w+)'", message)
    if found:
        kind, attribute = found.groups()
        if kind == "NoneType":
            return _missing_node(attribute, code)
        return API.get((kind, attribute)) or API.get((None, attribute)) or ""
    if "PermissionError" in message or "permission error" in message:
        return _locked(code)
    if "Invalid node type name" in message or (
            "OperationFailed" in message and "createNode" in code):
        return _node_type(code)
    if "Invalid menu item" in message:
        return ("A menu parameter got a value that is not one of its tokens. Read the "
                "tokens with node_inspect mode 'schema' and the parameter name, and set "
                "the token (a word like 'block'), not the label and not a guessed index.")
    if "Ambiguous call to function" in message:
        return ("VEX cannot tell which version of the function you mean. Cast the "
                "argument or the result to its type: float(rand(@ptnum)), "
                "len(array) with a typed array (int[] list = ...).")
    return ""


def _paths(code):
    return re.findall(r"""hou\.node\(\s*['"]([^'"]+)['"]\s*\)""", code)


def _missing_node(attribute, code):
    """`'NoneType' object has no attribute ...` after hou.node() found nothing."""
    lines = []
    for path in _paths(code):
        if hou.node(path) is None:
            lines.append(missing_path(path))
    if not lines:
        return (f"Something was None where the code read .{attribute}: most often "
                f"hou.node(path) found no node there, or a lookup by name found nothing. "
                f"Use need(path) instead of hou.node(path): it fails with the path and "
                f"the nodes that are there.")
    return " ".join(lines) + " Use need(path) instead of hou.node(path): it fails at " \
                             "once with this message."


def missing_path(path: str) -> str:
    """There is no node at path: say which part of it exists, and what is
    close to the part that does not."""
    parts = path.rstrip("/").split("/")
    parent = "/"
    for index in range(1, len(parts)):
        candidate = "/".join(parts[:index + 1]) or "/"
        if hou.node(candidate) is None:
            node = hou.node(parent)
            names = [child.name() for child in node.children()] if node else []
            close = difflib.get_close_matches(parts[index], names, n=4, cutoff=0.4)
            where = f"{parent} has no node '{parts[index]}'"
            if close:
                return f"hou.node('{path}') is None: {where}. Close: {', '.join(close)}."
            shown = ", ".join(names[:12]) + (" ..." if len(names) > 12 else "")
            return f"hou.node('{path}') is None: {where}. It holds: {shown or 'nothing'}."
        parent = candidate
    return f"hou.node('{path}') is None."


def need(path: str):
    """hou.node(path), or a clear error with what is there instead of None."""
    node = hou.node(path)
    if node is None:
        raise ValueError(missing_path(path))
    return node


def _locked(code):
    """Name the locked asset that refused the write, and what to do."""
    for path in _paths(code):
        node = hou.node(path)
        if node is None:
            continue
        owner = node
        while owner is not None and not owner.isLockedHDA():
            owner = owner.parent()
        if owner is not None and owner != node:
            return (f"{path} is inside the locked asset {owner.path()} "
                    f"({owner.type().name()}), and Houdini refuses changes inside a "
                    f"locked asset. Build next to it, in the network that holds it, or set "
                    f"the parameters that the asset shows on its top node. Unlock it "
                    f"(allowEditingOfContents) only when the user asks for it.")
    return ("Houdini refused a change to a locked node: a node inside a locked digital "
            "asset (for example inside a Karma or SOP Create LOP), or a parameter that "
            "an asset locks. Build next to the asset, not inside it; unlock it "
            "(allowEditingOfContents) only when the user asks for it. A disabled "
            "parameter is set through the parameter that enables it.")


def _node_type(code):
    """createNode got a type that this network does not have."""
    names = re.findall(r"""createNode\(\s*['"]([^'"]+)['"]""", code)
    known = {}
    for category in hou.nodeTypeCategories().values():
        for type_name in category.nodeTypes():
            known.setdefault(type_name, category.name())
    lines = []
    for name in names:
        if name in known:
            continue
        close = difflib.get_close_matches(name, list(known), n=5, cutoff=0.6)
        lines.append(f"There is no node type '{name}'."
                     + (f" Close: {', '.join(f'{c} ({known[c]})' for c in close)}."
                        if close else ""))
    return (" ".join(lines) + " A node type exists only in its own context (SOP, LOP, "
            "DOP, COP...): create it in a network of that context, and look the name up "
            "with the docs tool.").strip()
