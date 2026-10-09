"""What one node is: type, parameters, code, errors, and what feeds it."""
from . import as_list, unknown_mode
from ..handlers import animation, cache, chops, context, cops, dops, materials, nodes, \
    parameters, rendering, timing, vex

MUTATES = False

MODES = ("info", "parms", "schema", "changed", "names", "expression", "keyframes", "code",
         "cook_chain", "explain", "material", "image", "channels", "simulation",
         "render_settings", "cache", "time_dependency", "validate", "readers", "layout",
         "errors")

# Names that agents use for a mode, from the error log of real runs.
SYNONYMS = {"help": "explain", "error": "errors", "warnings": "errors", "parameters": "parms",
            "vex": "code", "snippet": "code"}


def run(paths, mode="info", parm=None, include_all_parms=False, object_name=None,
        field_name=None, channel=None, start=None, end=None, pattern=None,
        has_expression=False, frames=None, fields=None):
    """Inspect one node or a list of nodes. Every result names its path."""
    mode = SYNONYMS.get(mode, mode)
    if fields and mode not in ("parms", "changed"):
        raise ValueError(f"fields is read by mode 'parms' and mode 'changed', not by "
                         f"mode '{mode}'.")
    if pattern and mode not in ("parms", "changed", "schema", "names"):
        raise ValueError(f"pattern is read by modes 'parms', 'changed', 'schema' and "
                         f"'names', not by mode '{mode}'.")
    results = []
    for path in as_list(paths):
        try:
            results.append({"path": path, "result": _one(
                path, mode, parm, include_all_parms, object_name, field_name,
                channel, start, end, pattern, has_expression, frames, fields)})
        except Exception as error:
            # A list must not lose the nodes after the one that failed.
            results.append({"path": path, "error": f"{type(error).__name__}: {error}"})
    return results[0] if len(results) == 1 else {"count": len(results), "nodes": results}


def _one(path, mode, parm, include_all_parms, object_name, field_name, channel, start, end,
         pattern=None, has_expression=False, frames=None, fields=None):
    if mode == "time_dependency":
        return nodes.time_dependency(path, frames)
    if frames:
        # The same mode at each frame, with the playbar put back after.
        return timing.at_frames(frames, lambda: _one(
            path, mode, parm, include_all_parms, object_name, field_name, channel,
            start, end, pattern, has_expression, fields=fields))
    if mode == "info":
        return nodes.get_node_info(path, include_all_parms)
    if mode == "errors":
        return nodes.node_messages(path)
    if mode == "parms":
        return parameters.get_parameters(path, parm, pattern, has_expression,
                                         fields=fields)
    if mode == "schema":
        return parameters.get_parameter_schema(path, parm, pattern)
    if mode == "changed":
        return parameters.get_parameters(path, parm, pattern, has_expression,
                                         changed_only=True, fields=fields)
    if mode == "names":
        return nodes.name_parameters(path, pattern)
    if mode == "expression":
        _needs(parm, "expression", "a parameter name")
        return parameters.get_expression(path, parm)
    if mode == "keyframes":
        _needs(parm, "keyframes", "a parameter name")
        return animation.get_keyframes(path, parm)
    if mode == "code":
        return vex.get_wrangle_code(path)
    if mode == "cook_chain":
        return context.get_cook_chain(path)
    if mode == "explain":
        return context.explain_node(path)
    if mode == "material":
        return materials.get_material_info(path)
    if mode == "image":
        return cops.get_cop_info(path)
    if mode == "channels":
        if channel or start is not None or end is not None:
            return chops.get_chop_data(path, channel, start, end)
        return chops.list_chop_channels(path)
    if mode == "simulation":
        if field_name:
            _needs(object_name, "simulation", "object_name with field_name")
            return dops.get_dop_field(path, object_name, field_name)
        if object_name:
            return {"object": dops.get_dop_object(path, object_name),
                    "relationships": dops.get_dop_relationships(path, object_name)}
        return {"simulation": dops.get_simulation_info(path),
                "objects": dops.list_dop_objects(path),
                "memory": dops.get_sim_memory_usage(path)}
    if mode == "render_settings":
        return rendering.get_render_settings(path)
    if mode == "cache":
        return cache.get_cache_status(path)
    if mode == "validate":
        return nodes.validate_names(path)
    if mode == "layout":
        return nodes.layout_problems(path)
    if mode == "readers":
        _needs(parm, "readers", "a parameter name")
        return parameters.readers(path, parm)
    raise unknown_mode(mode, MODES)


def _needs(value, mode, what):
    if not value:
        raise ValueError(f"mode '{mode}' needs {what}.")
