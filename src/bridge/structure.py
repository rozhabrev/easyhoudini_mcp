"""The shape of the networks the agent leaves: checked in code, not only by a rule.

A run of 0.3/0.4 made a new subnet and new network boxes for every follow-up
request. A node sits in one box only, so each new box took the nodes of the
old one and left it empty; users got networks full of empty boxes with one
title and subnets that repeat each other (11.10.2026).

audit() reads every network of the scene in one call and reports, for the
nodes the agent made (the `ai` prefix and OUT_ nulls):
    stacked         nodes on one spot
    overlapping_nodes / overlapping_boxes  nodes or boxes drawn over each other
    outside_boxes   nodes outside network boxes (SOP, LOP, COP networks)
    empty_boxes     network boxes with nothing in them
    repeated_boxes  two or more boxes with one title in one network
    repeated_subnets subnets of one name with a number added (ai_wheel,
                    ai_wheel1)
    empty_subnets   subnets with nothing inside (at the save only)
    loose_ends      nodes that feed nothing and show nothing (at the save only)
    spread_out_boxes boxes far larger than their nodes: gaps in the chain
"""
import json

from .connection import call_json

AUDIT = r'''
import json, collections, re
report = []
nets = [hou.node("/obj"), hou.node("/stage")] + [n for n in hou.node("/").allSubChildren()
        if n.isNetwork() and n.children()]
seen = set()
for net in nets:
    # isEditable, not isInsideLockedHDA: a SOP Create sits inside a locked
    # asset, yet its network is the user's to edit, and was never checked.
    if net is None or net.path() in seen or not net.isEditable():
        continue
    seen.add(net.path())
    kids = [k for k in net.children() if k.type().name() not in ("subinput", "suboutput")]
    entry = {"network": net.path(), "nodes": len(kids)}
    # Only the agent's own nodes are judged: the user's nodes stay where the
    # user put them, and a report on them would send the agent to move them.
    def ours(k):
        return k.name().lower().startswith(("ai", "out_"))
    mine = [k for k in kids if ours(k)]
    if LAYOUT and len(mine) >= 4:
        pos = collections.Counter((round(k.position()[0], 1), round(k.position()[1], 1)) for k in kids)
        stacked = sum(1 for k in mine if pos[(round(k.position()[0], 1), round(k.position()[1], 1))] > 1)
        boxes_needed = net.childTypeCategory().name() in ("Sop", "Lop", "Cop")
        unboxed = [k.name() for k in mine if boxes_needed and not k.parentNetworkBox()]
        if stacked:
            entry["stacked"] = stacked
        # The name is drawn to the right of the node and belongs to its place:
        # a neighbour on top of the name makes both unreadable.
        rects = [(k.name(), k.position(), (k.size()[0] + 0.2 + 0.14 * len(k.name()), k.size()[1]), ours(k))
                 for k in kids]
        overlap = set()
        for i, (na, pa, sa, oa) in enumerate(rects):
            for nb, pb, sb, ob in rects[i + 1:]:
                if (oa or ob) and (pa[0] < pb[0] + sb[0] and pb[0] < pa[0] + sa[0]
                                   and pa[1] < pb[1] + sb[1] and pb[1] < pa[1] + sa[1]):
                    overlap.update(n for n, o in ((na, oa), (nb, ob)) if o)
        if overlap:
            entry["overlapping_nodes"] = sorted(overlap)[:10]
        brects = [b.comment() or b.name() for b in net.networkBoxes()]
        bpos = [(b.position(), b.size()) for b in net.networkBoxes()]
        crossed = set()
        for i, (pa, sa) in enumerate(bpos):
            for j in range(i + 1, len(bpos)):
                pb, sb = bpos[j]
                if (pa[0] < pb[0] + sb[0] and pb[0] < pa[0] + sa[0]
                        and pa[1] < pb[1] + sb[1] and pb[1] < pa[1] + sa[1]):
                    crossed.update((brects[i], brects[j]))
        if crossed:
            entry["overlapping_boxes"] = sorted(crossed)[:10]
        if unboxed:
            entry["outside_boxes"] = len(unboxed)
            entry["examples"] = unboxed[:5]
    if LAYOUT and net.childTypeCategory().name() in ("Sop", "Lop", "Cop"):
        # A node that feeds nothing and shows nothing is a leftover: the old
        # version of a part after a change, kept next to the new one.
        loose = [k.name() for k in mine if not k.outputs() and not k.name().upper().startswith(("OUT", "CTRL"))
                 and "ctrl" not in k.name().lower()
                 and not (hasattr(k, "isDisplayFlagSet") and (k.isDisplayFlagSet() or k.isRenderFlagSet()))
                 and not k.isBypassed() and k.type().name() not in ("null", "output", "rop_geometry", "filecache")]
        if loose:
            entry["loose_ends"] = loose[:10]
    boxes = net.networkBoxes()
    empty = [b.comment() or b.name() for b in boxes if not b.items()]
    if empty:
        entry["empty_boxes"] = empty[:10]
    if LAYOUT:
        # A box many times larger than its nodes: the chain is spread over the
        # canvas with gaps, and the reader hunts for the next node.
        loose_boxes = []
        for b in boxes:
            inside = [i for i in b.nodes() if ours(i)]
            if len(inside) >= 3 and b.size()[0] * b.size()[1] > 15 * len(inside):
                loose_boxes.append(b.comment() or b.name())
        if loose_boxes:
            entry["spread_out_boxes"] = loose_boxes[:10]
    titles = collections.Counter((b.comment() or "").strip().lower() for b in boxes if (b.comment() or "").strip())
    twice = [t for t, c in titles.items() if c > 1]
    if twice:
        entry["repeated_boxes"] = twice[:10]
    subnets = [k for k in kids if k.type().name() == "subnet" or k.type().name().endswith("::subnet")]
    stems = collections.Counter(re.sub(r"\d+$", "", s.name()) for s in subnets)
    repeated = sorted(s.name() for s in subnets if stems[re.sub(r"\d+$", "", s.name())] > 1)
    if repeated:
        entry["repeated_subnets"] = repeated[:10]
    hollow = [s.name() for s in subnets if not [c for c in s.children()
              if c.type().name() not in ("subinput", "suboutput")]]
    if LAYOUT and hollow:
        entry["empty_subnets"] = hollow[:10]
    if len(entry) > 2:
        report.append(entry)
print(json.dumps(report))
'''

STRUCTURE_KEYS = ("empty_boxes", "repeated_boxes", "repeated_subnets", "empty_subnets")
# Right after a call, a box made in this call can still be empty: the next
# call fills it. Only a repeat is wrong at once.
AT_ONCE = ("repeated_boxes", "repeated_subnets")


def audit(layout: bool = True) -> list:
    """The report for the whole scene. layout=False checks only boxes and
    subnets: mid-build, nodes outside boxes are normal, empty boxes are not."""
    try:
        out = json.loads(call_json("execute", {
            "source": f"LAYOUT = {bool(layout)}\n" + AUDIT, "mode": "python",
            "timeout": 30}, timeout=60.0))
        text = out.get("stdout") or out.get("output") or ""
        return json.loads(text.strip().splitlines()[-1]) if text.strip() else []
    except Exception as error:  # the check must never break the call it follows
        return [{"error": str(error)}]


# When a call makes a box or a subnet, the check runs right after it, so the
# agent fixes the structure before it builds on it, not at the save.
def makes_structure(name: str, arguments: dict) -> bool:
    if name == "node_edit":
        types = [arguments.get("node_type")] + [item.get("node_type") for item in
                                                 _items(arguments.get("items"))]
        return any(t and str(t).split("::")[0] == "subnet" for t in types)
    if name in ("execute", "batch"):
        text = json.dumps(arguments, default=str)
        return "createNetworkBox" in text or '"subnet"' in text or "'subnet'" in text
    return False


def _items(items):
    if isinstance(items, dict):
        return [items]
    return [item for item in items or [] if isinstance(item, dict)]


def note(name: str, arguments: dict) -> str:
    """A warning after a call that made a box or a subnet, when the scene now
    has empty boxes, repeated boxes or repeated subnets. Empty otherwise."""
    if not makes_structure(name, arguments):
        return ""
    problems = [entry for entry in audit(layout=False)
                if any(key in entry for key in AT_ONCE)]
    if not problems:
        return ""
    lines = []
    for entry in problems:
        parts = [f"{key.replace('_', ' ')}: {', '.join(entry[key])}"
                 for key in AT_ONCE if key in entry]
        lines.append(f"{entry['network']} - {'; '.join(parts)}")
    return ("The network now repeats itself: " + " | ".join(lines) + ". Work in the box "
            "or subnet that is already there: move the nodes into it, delete the empty "
            "and the repeated ones, and never make a second box or subnet for one block.")
