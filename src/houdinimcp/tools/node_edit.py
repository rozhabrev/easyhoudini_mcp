"""Make, move, name, delete and flag nodes.

Every mode takes one item or a list of items. Houdini adds a numeric suffix
when a name is already used, so each result carries the path that Houdini gave.
"""
from . import items_of, unknown_mode
from .. import hints
from ..handlers import chops, cops, lop, materials, nodes, takes, vex, viewport

MUTATES = True

MODES = ("create", "delete", "copy", "move", "rename", "flags", "color", "layout",
         "wrangle", "material", "assign_material", "take", "current_network")


def run(items=None, mode="create", **defaults):
    """Run one mode over one item or a list of items.

    An item is a dictionary of the arguments for the mode. Arguments given
    outside `items` are defaults for every item.
    """
    results = []
    for arguments in items_of(mode, items, defaults):
        try:
            results.append(_one(mode, arguments))
        except Exception as error:
            text = f"{type(error).__name__}: {error}"
            made = f"hou.node('{arguments.get('parent_path', '')}').createNode(" \
                   f"'{arguments.get('node_type', '')}')" if mode == "create" else ""
            failed = {"error": text, "item": arguments}
            hint = hints.hint(text, made)
            if hint:
                failed["hint"] = hint
            results.append(failed)
    return results[0] if len(results) == 1 else {"count": len(results), "results": results}


def _one(mode, item):
    if mode == "create":
        context = item.get("context", "sop")
        parent_path = item["parent_path"]
        node_type = item["node_type"]
        name = item.get("name")
        if context == "cop":
            return cops.create_cop_node(parent_path, node_type, name)
        if context == "chop":
            return chops.create_chop_node(parent_path, node_type, name)
        if context == "lop":
            return lop.create_lop_node(parent_path, node_type, name)
        if context == "material_network":
            return materials.create_material_network(parent_path, name or "matnet")
        return nodes.create_node(node_type, parent_path, name,
                                 item.get("position"), item.get("parameters"),
                                 item.get("input_path"))
    if mode == "delete":
        return nodes.delete_node(item["path"])
    if mode == "copy":
        return nodes.copy_nodes(item.get("paths") or [item["path"]],
                                item.get("destination_path"), item.get("suffix"),
                                item.get("names"))
    if mode == "move":
        if "destination_path" in item:
            return nodes.move_node(item["path"], item["destination_path"])
        return nodes.modify_node(item["path"], position=item.get("position"))
    if mode == "rename":
        return nodes.rename_node(item["path"], item["new_name"])
    if mode == "flags":
        target = item["path"]
        setter = cops.set_cop_flags if item.get("context") == "cop" else nodes.set_node_flags
        return setter(target, item.get("display"), item.get("render"), item.get("bypass"))
    if mode == "color":
        return nodes.set_node_color(item["path"], item["color"])
    if mode == "layout":
        return nodes.layout_children(item.get("path", "/obj"), item.get("paths"))
    if mode == "wrangle":
        if item.get("path"):
            return vex.write_snippet(item["path"], code=item.get("code"),
                                     code_file=item.get("code_file"),
                                     replace=item.get("replace"),
                                     parm=item.get("parm", "snippet"))
        if item.get("attrib_name"):
            return vex.create_vex_expression(item["parent_path"], item["attrib_name"],
                                             item["expression"], item.get("run_over", "Points"))
        return vex.create_wrangle(item["parent_path"], item.get("wrangle_type", "attribwrangle"),
                                  item.get("name"), item.get("code", ""),
                                  item.get("code_file"), item.get("input_path"))
    if mode == "material":
        return nodes.set_material(item["path"], item.get("material_type", "principledshader"),
                                  item.get("name"), item.get("parameters"))
    if mode == "assign_material":
        return materials.assign_material(item["path"], item["material_path"])
    if mode == "take":
        if item.get("name"):
            return takes.create_take(item["name"], item.get("parent_name"))
        return takes.set_current_take(item["take_name"])
    if mode == "current_network":
        return viewport.set_current_network(item["path"])
    raise unknown_mode(mode, MODES)
