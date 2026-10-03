"""One module for each MCP tool, mirroring src/bridge/tools/.

A tool module holds:
    MUTATES        True when the tool can change the scene. The dispatch puts a
                   mutating call in one undo group, so no hand-kept list of
                   command names can drift from the code.
    run(**params)  the work. Plain JSON in, plain JSON out.
"""
import importlib
import inspect
import pkgutil
import time

import hou

from ..handlers import autosave, timelapse

MODULES = sorted(module.name for module in pkgutil.iter_modules(__path__))


def dispatch(command: str, params: dict):
    """Run one tool. Wraps a mutating tool in one undo group, and tells the
    timelapse when it ends."""
    if command not in MODULES:
        raise ValueError(f"Unknown tool '{command}'. This plugin has: {', '.join(MODULES)}. "
                         f"The bridge and the plugin are different versions: run the "
                         f"installer again and restart Houdini.")
    module = importlib.import_module(f"{__name__}.{command}")
    if not getattr(module, "MUTATES", False):
        return module.run(**params)
    started = time.time()
    autosave.before(command, params)
    mark = timelapse.before(command)
    with hou.undos.group(f"MCP: {command}"):
        result = module.run(**params)
    if inspect.isgenerator(result):
        return _observed(command, params, result, started, mark)
    timelapse.after(command, params, started, result, mark)
    autosave.after(command)
    return result


def _observed(command, params, generator, started, mark):
    """A call that waits in the event loop changes the scene when it ends."""
    result = yield from generator
    timelapse.after(command, params, started, result, mark)
    autosave.after(command)
    return result


def as_list(value):
    """One item or a list of items, always as a list."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class Arguments(dict):
    """The arguments of one item. A missing one names itself and the mode,
    because a bare KeyError says nothing about what the call lacks."""

    def __init__(self, mode, values):
        super().__init__(values)
        self.mode = mode

    def __missing__(self, key):
        raise ValueError(f"mode '{self.mode}' needs the argument '{key}'.")


def items_of(mode, items, defaults):
    """One item or a list of them, each merged over the defaults."""
    return ([Arguments(mode, {**defaults, **item}) for item in as_list(items)]
            or [Arguments(mode, defaults)])


def unknown_mode(mode, known):
    return ValueError(f"Unknown mode '{mode}'. Use one of: {', '.join(known)}.")
