"""Lists: what is in the scene, and what the scene can use."""
from . import unknown_mode
from ..handlers import cache, context, lop, materials, nodes, rendering, scene, takes, viewport

MUTATES = False

MODES = ("scene", "network", "children", "search", "node_types", "errors",
         "materials", "lights", "takes", "caches", "render_nodes", "viewports")


def run(mode="scene", path=None, pattern=None, node_type=None, category=None,
        recursive=False):
    if mode == "scene":
        return {"scene": scene.get_scene_info(), "summary": context.get_scene_summary()}
    if mode == "network":
        return context.get_network_overview(path or "/obj")
    if mode == "children":
        return nodes.list_children(path or "/obj", recursive)
    if mode == "search":
        if not pattern:
            raise ValueError("mode 'search' needs a pattern, for example 'geo*'.")
        return nodes.find_nodes(pattern, node_type, path or "/")
    if mode == "node_types":
        return nodes.list_node_types(category, pattern)
    if mode == "errors":
        return nodes.find_error_nodes(path or "/obj")
    if mode == "materials":
        return {"materials": materials.list_materials(path or "/mat"),
                "types": materials.list_material_types()}
    if mode == "lights":
        if not path:
            raise ValueError("mode 'lights' needs the path of a LOP node.")
        return lop.list_lights(path)
    if mode == "takes":
        return {"takes": takes.list_takes(), "current": takes.get_current_take()}
    if mode == "caches":
        return cache.list_caches(path or "/obj")
    if mode == "render_nodes":
        return rendering.list_render_nodes()
    if mode == "viewports":
        return {"panes": viewport.list_panes(), "viewport": viewport.get_viewport_info()}
    raise unknown_mode(mode, MODES)
