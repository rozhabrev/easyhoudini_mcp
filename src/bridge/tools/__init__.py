"""The MCP tool surface. One module for each tool, found by its file name.

A tool module holds:
    tool(...)     the function that the client calls. Its name is the module
                  name, its docstring is what the client reads.
    ANNOTATIONS   optional ToolAnnotations, for example destructiveHint.
"""
import functools
import importlib
import json
import inspect
import pkgutil
from typing import Optional

from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.mcpserver.tools import Tool
from mcp.server.mcpserver.utilities.func_metadata import FuncMetadata

from .. import errors

# name -> Tool, filled by build(). batch validates its steps against these.
TOOLS = {}

# The house rules go to the agent with the first result of this process. A
# client can cut the server instructions short, and a result it always reads.
RULES = {"text": "", "sent": False}


def build(rules: str = "") -> list:
    """Every tool module in this package, as MCP tools."""
    RULES["text"] = rules
    for name in sorted(module.name for module in pkgutil.iter_modules(__path__)):
        module = importlib.import_module(f"{__name__}.{name}")
        if not hasattr(module, "tool"):
            continue
        tool = Tool.from_function(_guarded(module.tool, name), name=name,
                                  annotations=getattr(module, "ANNOTATIONS", None))
        # An argument that the tool does not take is refused, not dropped: a
        # dropped filter returns everything and reads as a filter that matched.
        model = tool.fn_metadata.arg_model
        model.model_config["extra"] = "forbid"
        model.model_rebuild(force=True)
        tool.parameters = model.model_json_schema(by_alias=True)
        tool.fn_metadata = _Metadata.model_construct(**{
            key: getattr(tool.fn_metadata, key) for key in FuncMetadata.model_fields})
        TOOLS[name] = tool
    return list(TOOLS.values())


class _Metadata(FuncMetadata):
    """The SDK reads a text argument as JSON when the type of the argument is
    not plain `str`, so that a list sent as text becomes a list. An optional
    argument is not plain `str`, and then the text "null" becomes nothing and
    "true" a boolean: node_type "null" was lost. Text that reads as null or as
    a boolean stays text; a list or an object is still read."""

    def pre_parse_json(self, data):
        parsed = super().pre_parse_json(data)
        return {key: data[key] if isinstance(data[key], str)
                and (value is None or isinstance(value, bool)) else value
                for key, value in parsed.items()}


def validate(name: str, params: dict) -> None:
    """Refuse the arguments of one call the way the client call would."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"There is no tool '{name}'. Tools: {', '.join(TOOLS)}.")
    tool.fn_metadata.validate_arguments(params)


def _guarded(function, name: str = ""):
    """The tool function, with two rules that every tool shares.

    An optional argument accepts null and then takes its default: a client
    sends null for an argument it leaves out, and a refusal that names an
    argument the caller never gave says nothing useful.

    Every failure keeps its text. The MCP SDK hides the text of any exception
    that is not a ToolError and sends only "Error executing tool <name>".
    """
    for parameter in inspect.signature(function).parameters.values():
        if parameter.default is not inspect.Parameter.empty and \
                parameter.annotation is not inspect.Parameter.empty:
            function.__annotations__[parameter.name] = Optional[parameter.annotation]

    @functools.wraps(function)
    def guarded(**arguments):
        given = {key: value for key, value in arguments.items() if value is not None}
        errors.tick()
        try:
            result = function(**given)
        except ToolError as error:
            raise ToolError(_noted(str(error), _logged(name, given, str(error)))) from error
        except Exception as error:
            text = f"{type(error).__name__}: {error}"
            raise ToolError(_noted(text, _logged(name, given, text))) from error
        notes = [_logged(name, given, text) for text in errors.soft_errors(result)]
        notes.append(_unsaved(name, given))
        result = _with_note(result, " ".join(note for note in notes if note))
        return _with_topics(_with_rules(result), name, given)

    return guarded


# Tools that change the scene, and the scene_file modes that write it to
# disk. The bridge counts the changes since the last save: an agent that never
# saved lost a whole run to one crash (09.10.2026), though the rule said save.
CHANGES = {"node_edit", "connect", "parm_set", "execute", "batch", "hda", "cook"}
SAVE_EVERY = 10
_unsaved_calls = {"count": 0}


def _unsaved(name: str, arguments: dict) -> str:
    mode = arguments.get("mode")
    if name == "scene_file" and mode in ("save", "load"):
        _unsaved_calls["count"] = 0
        return ""
    if name not in CHANGES or (name == "execute" and mode == "job"):
        return ""
    _unsaved_calls["count"] += 1
    count = _unsaved_calls["count"]
    if count < SAVE_EVERY or (count - SAVE_EVERY) % 5:
        return ""
    return (f"The scene has not been saved for {count} calls that change it. Save a new "
            f"version now (scene_file mode='save' with a new path), or a crash loses "
            f"all of it.")


def _logged(name: str, arguments: dict, message: str) -> str:
    """Write the error to the log. Returns the note for a repeated error."""
    from ..connection import last_version
    code = arguments.get("source")
    if name == "batch":
        code = json.dumps(arguments.get("operations"), default=str)
    return errors.record(name, message, mode=arguments.get("mode") or arguments.get("action"),
                         code=code, version=last_version())


def _noted(text: str, note: str) -> str:
    return f"{text}\n\n{note}" if note else text


def _with_note(result, note: str):
    if not note:
        return result
    if isinstance(result, list):
        return result + [note]
    return f"{result}\n\n{note}"


def _with_topics(result, name: str, arguments: dict):
    """The result, with the rules of each topic this call works in and the
    agent has not read yet."""
    from . import topics
    due = topics.due(name, arguments)
    if not due:
        return result
    for topic in due:
        topics.mark_sent(topic)
    text = "This call works in a topic of the house rules that you have not " \
           "read. Read it before your next call.\n\n" + \
           "\n\n".join(topics.read(topic) for topic in due)
    if isinstance(result, list):
        return result + [text]
    return f"{result}\n\n{text}"


def _with_rules(result):
    """The result, with the house rules after it the first time."""
    if RULES["sent"] or not RULES["text"]:
        return result
    RULES["sent"] = True
    rules = "Read these rules before your next call.\n\n" + RULES["text"]
    if isinstance(result, list):
        return result + [rules]
    return f"{result}\n\n{rules}"
