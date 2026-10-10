"""Tools that the person writes. A Python file in a tools folder, one function
in it marked with @tool, and the agent can call it through the `custom` tool.

    from houdinimcp.custom import tool

    @tool
    def balls_on_grid(parent: str = "/obj", count: int = 50) -> dict:
        '''What the agent reads: what it does, when to use it, what it returns.'''
        ...

The folders: `easyhoudini_mcp/tools` in the Houdini user preferences folder,
and every folder in the environment variable HOUDINIMCP_TOOLS. A file is read
again when it changes, so an edit works without restarting Houdini.
"""
import importlib.util
import inspect
import os
import sys
import typing

import hou

ENV = "HOUDINIMCP_TOOLS"

# path -> {"mtime", "tools": {name: function}, "error"}
_FILES = {}


def tool(function=None, *, mutates=True):
    """Mark a function as a tool. mutates=False for a tool that only reads:
    it then runs outside an undo group and takes no timelapse frame."""
    def mark(fn):
        fn._houdinimcp_tool = {"mutates": bool(mutates)}
        return fn
    return mark(function) if function is not None else mark


def folders() -> list:
    found = []
    prefs = hou.text.expandString("$HOUDINI_USER_PREF_DIR")
    if prefs and not prefs.startswith("$"):
        found.append(os.path.join(prefs, "easyhoudini_mcp", "tools"))
    for folder in os.environ.get(ENV, "").split(os.pathsep):
        if folder.strip():
            found.append(os.path.expanduser(folder.strip()))
    return found


def _files():
    for folder in folders():
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith(".py") and not name.startswith("_"):
                yield os.path.join(folder, name)


def _read(path):
    """The tools of one file, read again only when the file changed."""
    mtime = os.path.getmtime(path)
    known = _FILES.get(path)
    if known and known["mtime"] == mtime:
        return known
    entry = {"mtime": mtime, "tools": {}, "error": None}
    stem = os.path.splitext(os.path.basename(path))[0]
    module_name = f"houdinimcp_user_{abs(hash(path))}_{stem}"
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        entry["tools"] = {name: value for name, value in vars(module).items()
                          if callable(value) and hasattr(value, "_houdinimcp_tool")}
    except Exception as error:
        entry["error"] = f"{type(error).__name__}: {error}"
    _FILES[path] = entry
    return entry


def load():
    """(tools, problems). tools: name -> (function, path). The first file in
    folder order wins a name; a second one is a problem, not a silent swap."""
    tools, problems = {}, []
    for path in _files():
        entry = _read(path)
        if entry["error"]:
            problems.append({"file": path, "error": entry["error"]})
        for name, function in entry["tools"].items():
            if name in tools:
                problems.append({"file": path, "error": f"tool '{name}' is already in "
                                 f"{tools[name][1]}; this one is not used."})
                continue
            tools[name] = (function, path)
    return tools, problems


_JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean",
               list: "array", tuple: "array", dict: "object"}


def _json_type(annotation):
    if annotation is inspect.Parameter.empty:
        return None
    origin = typing.get_origin(annotation)
    if origin is typing.Union:
        kinds = [_json_type(arg) for arg in typing.get_args(annotation)
                 if arg is not type(None)]
        kinds = [kind for kind in kinds if kind]
        return kinds[0] if len(kinds) == 1 else None
    return _JSON_TYPES.get(origin or annotation)


def describe(name, function, path) -> dict:
    """What the agent reads about one tool: its text and its arguments."""
    arguments = {}
    for parameter in inspect.signature(function).parameters.values():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        argument = {}
        kind = _json_type(parameter.annotation)
        if kind:
            argument["type"] = kind
        if parameter.default is parameter.empty:
            argument["required"] = True
        else:
            argument["default"] = parameter.default
        arguments[parameter.name] = argument
    return {"name": name, "description": inspect.getdoc(function) or "",
            "arguments": arguments, "mutates": function._houdinimcp_tool["mutates"],
            "file": path}


def find(name):
    """(function, path) of one tool, or a ValueError that lists the tools."""
    tools, problems = load()
    if name in tools:
        return tools[name]
    broken = [problem["file"] for problem in problems]
    raise ValueError(f"There is no custom tool '{name}'. Custom tools: "
                     f"{', '.join(tools) or 'none'}."
                     + (f" Files with problems (mode 'list' says which): {', '.join(broken)}." if broken else ""))


def mutates(name) -> bool:
    try:
        function, _ = find(name)
    except ValueError:
        return False
    return function._houdinimcp_tool["mutates"]


def call(name, params):
    function, _ = find(name)
    try:
        bound = inspect.signature(function).bind(**(params or {}))
    except TypeError as error:
        arguments = ", ".join(inspect.signature(function).parameters) or "none"
        raise ValueError(f"{name}: {error}. Its arguments: {arguments}.") from error
    return function(*bound.args, **bound.kwargs)
