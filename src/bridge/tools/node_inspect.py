"""node_inspect — everything about one node, or about a list of nodes."""
from typing import Any, Dict, List, Union

from ..connection import call_json


def tool(paths: Union[str, List[str]], mode: str = "info", parm: str = None,
         include_all_parms: bool = False, object_name: str = None,
         field_name: str = None, channel: str = None,
         start: float = None, end: float = None, pattern: str = None,
         has_expression: bool = False,
         frames: Union[float, List[float], Dict[str, float]] = None,
         fields: List[str] = None) -> str:
    """Read one node, or a list of nodes, without changing anything.

    Use it before you write: to confirm a parameter name, to see whether a
    parameter carries an expression, and to read what a node reports after a
    cook.

    Do not use it to list a network: scene_overview does that.

    paths: one node path, or a list of them. A list keeps going after a node
    that fails, and each result names its path.

    mode:
        "info"            — type, inputs, outputs, flags, changed parameters.
        "errors"          — the errors, warnings and messages on the node, and
                            whether it needs to cook.
        "parms"           — every parameter, or one parameter when you give
                            `parm`. The result says whether the value comes
                            from an expression.
        "schema"          — the parameter templates: types, ranges, menus.
                            Read this before you write a menu parameter.
        "changed"         — only the parameters that a person set: not at the
                            default, or with an expression or keys. Folders,
                            labels, buttons and hidden fields are left out, and
                            a ramp is one entry with its keys.
        "names"           — the names of the parameters, and nothing else. Read
                            this first when you do not know the name to write.
        "expression"      — the expression on `parm`, and its language.
        "keyframes"       — the keys on `parm`.
        "code"            — the VEX snippet in a wrangle node.
        "cook_chain"      — what this node cooks from, upstream.
        "explain"         — a short account of what the node does here.
        "material"        — the shader parameters of a material node.
        "image"           — the COP node: resolution, planes, data type.
        "channels"        — CHOP channels. `channel`, `start` and `end` read
                            the samples of one channel.
        "simulation"      — the DOP network. `object_name` reads one object,
                            with `field_name` one field of it.
        "render_settings" — the parameters of a ROP node.
        "cache"           — the file cache state of a node.
        "time_dependency" — which nodes under this one cook again on every
                            frame, and what makes each one do it. With
                            `frames` it times each one and sorts by the time.
        "validate"        — the names in the parameters of the node that name
                            nothing: a group, an attribute or a volume that the
                            input geometry does not hold. That is the failure
                            that gives a wrong result with no error.
        "layout"          — for a network: each node that sits above its input,
                            and each pair of nodes in one slot, where one name
                            covers the other. Read it after you add nodes.
        "readers"         — the parameters that read `parm` through a channel
                            reference or an expression: what else a write to
                            it changes.

    pattern: keep the parameters whose name or label holds this text, or
    matches it as a glob. "|" separates alternatives: "time|step|cfl".
    has_expression: keep only the parameters that carry an expression.
    fields: keep only these keys of each parameter in "parms" and "changed",
    for example ["value", "expression"]. The name is always kept. A solver has
    hundreds of parameters: give pattern or fields.

    frames: read the same mode at another frame, or at several: one frame, a
    list of frames, or {"start": 1, "end": 10, "step": 2}. The playbar goes
    back to where it was.

    Returns JSON. A cook error comes back in the result: an empty geometry with
    no error line means the node cooked and made nothing.
    """
    return call_json("node_inspect", {
        "paths": paths, "mode": mode, "parm": parm,
        "include_all_parms": include_all_parms, "object_name": object_name,
        "field_name": field_name, "channel": channel, "start": start, "end": end,
        "pattern": pattern, "has_expression": has_expression, "frames": frames,
        "fields": fields,
    })
