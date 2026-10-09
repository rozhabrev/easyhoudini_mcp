"""COP (compositing) handlers."""
import hou


def get_cop_info(path):
    """Get info about a COP node: resolution and planes for an old COP2 node,
    the layer of each output for a Copernicus node."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    if hasattr(node, "planes"):
        return {
            "path": node.path(),
            "type": node.type().name(),
            "xres": node.xRes(),
            "yres": node.yRes(),
            "planes": list(node.planes()),
        }
    # Copernicus: no planes, one layer (or geometry, or a VDB) for each output.
    outputs = []
    for index, label in enumerate(node.outputLabels()):
        entry = {"output": index, "label": label}
        try:
            layer = node.layer(index)
            entry.update(resolution=list(layer.bufferResolution()),
                         channels=layer.channelCount())
        except Exception as error:
            entry["layer"] = f"not an image layer ({type(error).__name__})"
        outputs.append(entry)
    return {"path": node.path(), "type": node.type().name(), "outputs": outputs}


def get_cop_geometry(path):
    """Get geometry data from a COP node (if applicable)."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    geo = node.geometry()
    if not geo:
        raise ValueError(f"No geometry on COP: {path}")
    return {
        "path": node.path(),
        "num_points": len(geo.points()),
        "num_prims": len(geo.prims()),
    }


def get_cop_layer(path, plane_name="C"):
    """Get info about a specific plane/layer in a COP node."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    planes = node.planes()
    if plane_name not in planes:
        raise ValueError(f"Plane not found: {plane_name}")
    return {
        "path": path,
        "plane": plane_name,
        "depth": str(node.depth(plane_name)),
        "components": node.components(plane_name),
    }


def create_cop_node(parent_path, node_type, name=None):
    """Create a COP node."""
    parent = hou.node(parent_path)
    if not parent:
        raise ValueError(f"Parent not found: {parent_path}")
    node = parent.createNode(node_type, node_name=name)
    return {"path": node.path(), "name": node.name(), "type": node_type}


def set_cop_flags(node_path, display=None, render=None, bypass=None):
    """Set display/render/bypass flags on a COP node."""
    node = hou.node(node_path)
    if not node:
        raise ValueError(f"Node not found: {node_path}")
    changes = []
    if display is not None:
        node.setDisplayFlag(display)
        changes.append(f"display={display}")
    if render is not None:
        node.setRenderFlag(render)
        changes.append(f"render={render}")
    if bypass is not None:
        node.bypass(bypass)
        changes.append(f"bypass={bypass}")
    return {"path": node.path(), "changes": changes}


def list_cop_node_types():
    """List available COP node types."""
    result = []
    for cat_name, cat in hou.nodeTypeCategories().items():
        if "Cop" not in cat_name:
            continue
        for name, nt in cat.nodeTypes().items():
            result.append({
                "name": name,
                "category": cat_name,
                "label": nt.description(),
            })
    return {"count": len(result), "types": result}


def get_cop_vdb(path):
    """Get VDB info from a COP node (for volume COP operations)."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    geo = node.geometry()
    if not geo:
        raise ValueError(f"No geometry on COP: {path}")
    vdbs = []
    for prim in geo.prims():
        if hasattr(prim, "resolution"):
            vdbs.append({
                "name": prim.attribValue("name") if geo.findPrimAttrib("name") else str(prim.number()),
                "resolution": list(prim.resolution()),
            })
    return {"path": path, "vdbs": vdbs}
