"""Autosave: a backup of the scene before a heavy step and every few minutes.

A rule that tells the agent to save is not enough: a run built two stages,
never saved, and lost all of it when Houdini quit on a fracture. So the
plugin saves a backup itself, with hou.hipFile.saveAsBackup: it writes
$HIP/backup/<name>_bak<N>.hip and leaves the open file and its versions
alone.

    before a call that can cook for long: a heavy node is made, a cook, a
    render, or an execute that names a heavy node type;
    after a change, when the last backup is older than INTERVAL_S.

HOUDINIMCP_AUTOSAVE=0 turns it off.
"""
import os
import time

import hou

from .follow import HEAVY

INTERVAL_S = 600

try:
    STATE  # noqa: B018  importlib.reload keeps the module namespace
except NameError:
    STATE = {"last": 0.0, "count": 0, "last_path": None, "last_error": None}


def enabled() -> bool:
    value = os.environ.get("HOUDINIMCP_AUTOSAVE", "1").strip().lower()
    return value not in ("", "0", "false", "off", "no")


def _types(params):
    """The node types that a node_edit call makes."""
    items = params.get("items")
    items = items if isinstance(items, list) else [items] if isinstance(items, dict) else []
    return [str(item.get("node_type") or "") for item in items] + [str(params.get("node_type") or "")]


def heavy_call(command, params) -> bool:
    if command == "node_edit" and params.get("mode", "create") == "create":
        return any(HEAVY.search(name) for name in _types(params) if name)
    if command == "render":
        return params.get("mode", "start") == "start"
    if command == "cook":
        # A cook of one frame to read errors is quick; a cache, a simulation
        # step, a range of frames or a heavy node is not.
        paths = params.get("paths")
        paths = paths if isinstance(paths, list) else [paths]
        nodes = [hou.node(path) for path in paths if isinstance(path, str)]
        return (params.get("mode", "cook") != "cook" or bool(params.get("frames"))
                or bool(params.get("frame_range"))
                or any(node is not None and HEAVY.search(node.type().name()) for node in nodes))
    if command == "execute":
        return bool(HEAVY.search(str(params.get("source") or "")))
    return False


def save(reason):
    """Write a backup when the scene is saved somewhere and has changes."""
    if not enabled() or hou.hipFile.isNewFile() or not hou.hipFile.hasUnsavedChanges():
        return None
    try:
        path = hou.hipFile.saveAsBackup()
    except hou.Error as error:
        STATE["last_error"] = f"{reason}: {error}"
        return None
    STATE.update(last=time.time(), count=STATE["count"] + 1, last_path=path,
                 last_error=None)
    return path


def before(command, params):
    """Called before each call of a tool with MUTATES."""
    if command != "batch" and heavy_call(command, params):
        save(f"before {command}")


def after(command):
    """Called after each call of a tool with MUTATES that did not fail."""
    if time.time() - STATE["last"] >= INTERVAL_S:
        save(f"after {command}")
