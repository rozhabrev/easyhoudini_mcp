"""PDG/TOPs handlers."""
import json

import hou


def pdg_cook(path):
    """Start cooking a TOP network (non-blocking)."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    node.executeGraph(False, False, False, False)
    result = {"cooking": True, "path": node.path()}
    if hou.hipFile.hasUnsavedChanges():
        result["warning"] = ("The scene has unsaved changes. Jobs that run out of "
                             "process load the .hip from disk and do not see them: "
                             "cancel, save, dirty and cook again.")
    return result


def pdg_status(path):
    """Get cook status and work item counts for a TOP network."""
    import pdg
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    pdg_node = node.getPDGNode()
    if not pdg_node:
        raise ValueError(f"No PDG node for: {path}")
    counts = {"waiting": 0, "cooking": 0, "cooked": 0, "failed": 0}
    for wi in pdg_node.workItems:
        state = wi.state
        if state == pdg.workItemState.CookedSuccess:
            counts["cooked"] += 1
        elif state == pdg.workItemState.Cooking:
            counts["cooking"] += 1
        elif state == pdg.workItemState.Waiting:
            counts["waiting"] += 1
        elif state == pdg.workItemState.CookedFail:
            counts["failed"] += 1
    counts["total"] = sum(counts.values())
    return {"path": node.path(), **counts}


def pdg_workitems(path, state=None):
    """List work items for a TOP node, optionally filtered by state."""
    import pdg
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    pdg_node = node.getPDGNode()
    if not pdg_node:
        raise ValueError(f"No PDG node for: {path}")
    items = []
    for wi in pdg_node.workItems:
        wi_state = str(wi.state)
        if state and state.lower() not in wi_state.lower():
            continue
        item = {
            "id": wi.id,
            "index": wi.index,
            "state": wi_state,
            "output_files": [f.path for f in wi.outputFiles],
        }
        if wi.state == pdg.workItemState.CookedFail:
            item["log"] = getattr(wi, "logURI", None) or None
        items.append(item)
    return {"path": node.path(), "count": len(items), "work_items": items}


def pdg_dirty(path, dirty_all=False):
    """Dirty work items on a TOP node for re-cooking."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    pdg_node = node.getPDGNode()
    if not pdg_node:
        raise ValueError(f"No PDG node for: {path}")
    if dirty_all:
        pdg_node.dirtyAllTasks(True)
    else:
        pdg_node.dirty(True)
    return {"dirtied": True, "path": node.path(), "all": dirty_all}


def pdg_cancel(path):
    """Cancel a running PDG cook."""
    node = hou.node(path)
    if not node:
        raise ValueError(f"Node not found: {path}")
    context = node.getPDGGraphContext()
    if not context:
        raise ValueError(f"No PDG context for: {path}")
    context.cancelCook()
    return {"cancelled": True, "path": node.path()}


# --- Parallel renders: one ROP, several variants, one TOP network ----------

# The parameter that holds the output image, by ROP type. The first one the
# copy has wins.
OUTPUT_PARMS = ("picture", "outputimage", "vm_picture", "sopoutput", "lopoutput")

GENERATE = '''import json
for index, variant in enumerate(json.loads(r"""{data}""")):
    item = item_holder.addWorkItem(index=index)
    for name, value in variant.items():
        values = value if isinstance(value, list) else [value]
        if all(isinstance(v, int) for v in values):
            setter, cast = item.setIntAttrib, int
        elif all(isinstance(v, (int, float)) for v in values):
            setter, cast = item.setFloatAttrib, float
        else:
            setter, cast = item.setStringAttrib, str
        for position, v in enumerate(values):
            setter(name, cast(v), position)
'''


def generate_script(variants):
    """The onGenerate code of the node that makes one work item per variant."""
    data = json.dumps(variants)
    if '"""' in data:
        raise ValueError("A variant value holds three double quotes in a row.")
    return GENERATE.format(data=data)


def variant_output(path, root):
    """The output path of the original ROP, moved into a folder per variant:
    $HIP/render/hero.$F4.exr -> <root>/`@variant`/hero.`@variant`.$F4.exr."""
    path = path or "$HIP/render/$OS.$F4.exr"
    name = path.replace("\\", "/").rsplit("/", 1)[-1]
    stem, dot, rest = name.partition(".")
    if not dot:
        stem, rest = name, "$F4.exr"
    return f"{root}/`@variant`/{stem}.`@variant`.{rest}"


def check_variants(variants):
    if not variants:
        raise ValueError("variants is empty: give a list like "
                         '[{"variant": "front", "camera": "/cameras/front"}, ...].')
    names = []
    for index, variant in enumerate(variants):
        if not isinstance(variant, dict):
            raise ValueError(f"variants[{index}] is not an object.")
        name = str(variant.get("variant") or variant.get("name") or "").strip()
        if not name or not all(c.isalnum() or c in "_-" for c in name):
            raise ValueError(f"variants[{index}] needs a `variant` name of letters, "
                             f"digits, - and _: it names the output folder.")
        names.append(name)
    if len(set(names)) != len(names):
        raise ValueError(f"Two variants have the same name: {names}.")
    return [{**{k: v for k, v in variant.items() if k != "name"}, "variant": name}
            for variant, name in zip(variants, names)]


def _set_menu(parm, label):
    """Set a menu parameter by the words of its label, since tokens change
    between versions. Returns the label it set, or None."""
    if parm is None:
        return None
    wanted = label.lower()
    for token, text in zip(parm.menuItems(), parm.menuLabels()):
        if wanted in text.lower():
            parm.set(token)
            return text
    return None


def _wire(rop, variant_keys):
    """Point the parameters of the ROP copy at the work item attributes of
    the same name. A key that names no parameter is reported, not lost."""
    wired, unused = {}, []
    for key in variant_keys:
        if key == "variant":
            continue
        tuple_parm = rop.parmTuple(key)
        if tuple_parm is None:
            unused.append(key)
            continue
        if len(tuple_parm) == 1:
            parm = tuple_parm[0]
            if parm.parmTemplate().type() == hou.parmTemplateType.String:
                parm.set(f"`@{key}`")
            else:
                parm.setExpression(f"@{key}", hou.exprLanguage.Hscript)
        else:
            for index, parm in enumerate(tuple_parm):
                parm.setExpression(f"@{key}.{index}", hou.exprLanguage.Hscript)
        wired[key] = tuple_parm.name()
    return wired, unused


def render_setup(path, variants, parallel=2, frame_range=None, name=None,
                 parent_path="/obj", output_root="$HIP/render/variants",
                 frames_per_batch=1):
    """Build a TOP network that renders the ROP at `path` once per variant,
    `parallel` jobs at a time. The original ROP is not touched: the network
    renders a copy whose parameters read the work item attributes."""
    import pdg  # noqa: F401  (fails early outside a PDG-capable Houdini)
    rop = hou.node(path)
    if rop is None:
        raise ValueError(f"Node not found: {path}")
    variants = check_variants(variants)
    keys = sorted({key for variant in variants for key in variant})
    parent = hou.node(parent_path)
    if parent is None:
        raise ValueError(f"Node not found: {parent_path}")

    copy = hou.copyNodesTo([rop], rop.parent())[0]
    copy.setName(f"{rop.name()}_variants", unique_name=True)
    copy.setPosition(rop.position() + hou.Vector2(0, -1.5))
    copy.setComment("Rendered by the TOP network " + (name or "render_variants")
                    + ": parameters read work item attributes (@variant, ...).")
    copy.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    wired, unused = _wire(copy, keys)
    output = None
    for parm_name in OUTPUT_PARMS:
        parm = copy.parm(parm_name)
        if parm is not None:
            output = {"parm": parm_name,
                      "path": variant_output(parm.unexpandedString(), output_root)}
            parm.deleteAllKeyframes()
            parm.set(output["path"])
            break

    topnet = parent.createNode("topnet", name or "render_variants")
    scheduler = next((child for child in topnet.children()
                      if child.type().name() == "localscheduler"), None)
    if scheduler is None:
        scheduler = topnet.createNode("localscheduler")
    slots = _set_menu(scheduler.parm("maxprocsmenu"), "custom")
    if scheduler.parm("maxprocs") is not None:
        scheduler.parm("maxprocs").set(int(parallel))
    if topnet.parm("topscheduler") is not None:
        topnet.parm("topscheduler").set(scheduler.path())

    items = topnet.createNode("pythonprocessor", "variants")
    items.parm("generate").set(generate_script(variants))
    fetch = topnet.createNode("ropfetch", "render")
    fetch.setInput(0, items)
    fetch.parm("roppath").set(copy.path())
    frames = None
    if frame_range:
        frames = _set_menu(fetch.parm("framegeneration"), "custom range")
        start, end = frame_range[0], frame_range[-1]
        step = frame_range[2] if len(frame_range) > 2 else 1
        fetch.parmTuple("range").set((start, end, step))
    if fetch.parm("framesperbatch") is not None:
        fetch.parm("framesperbatch").set(int(frames_per_batch))
    wait = topnet.createNode("waitforall", "all_done")
    wait.setInput(0, fetch)
    wait.setDisplayFlag(True)
    topnet.layoutChildren()
    topnet.moveToGoodPosition()

    report = {
        "topnet": topnet.path(), "items": items.path(), "render": fetch.path(),
        "rop_copy": copy.path(), "original_rop": rop.path(),
        "variants": [variant["variant"] for variant in variants],
        "parallel": int(parallel), "scheduler_slots": slots,
        "wired": wired, "output": output,
        "frame_range": frame_range, "frame_mode": frames,
        "next": "Save the scene, then pdg mode=cook path=" + wait.path()
                + ": each job loads the .hip from disk, unsaved changes are not rendered.",
    }
    if unused:
        report["warning"] = (f"No parameter on {copy.path()} is named {unused}. "
                             f"Those attributes reach the work items but change "
                             f"nothing. Use the real parameter names of the ROP.")
    if output is None:
        report["warning_output"] = ("The ROP copy has no known output parameter: "
                                    "all variants may write to the same file.")
    if frame_range and frames is None:
        report["warning_frames"] = "Could not set a custom range on the ROP Fetch."
    return report
