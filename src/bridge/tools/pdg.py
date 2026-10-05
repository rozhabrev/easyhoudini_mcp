"""pdg — TOP networks and their work items."""
from typing import List

from ..connection import call_json


def tool(path: str, mode: str = "status", state: str = None,
         dirty_all: bool = False, variants: List[dict] = None,
         parallel: int = 2, frame_range: List[float] = None, name: str = None,
         parent_path: str = "/obj", output_root: str = "$HIP/render/variants",
         frames_per_batch: int = 1) -> str:
    """Cook a TOP network, read what its work items did, or build one that
    renders several variants of a shot in parallel.

    Use it for a TOP network only. A TOP node does not cook like a SOP: it
    makes work items, and each item runs on its own.

    path: the TOP network or the TOP node; for "render_setup", the ROP.

    mode:
        "status"       — the counts for each state, and whether a cook runs now.
        "workitems"    — the items. `state` filters, for example "failed".
        "cook"         — start the cook. The call comes back at once; read
                         "status" after it to follow the work.
        "dirty"        — mark the node dirty. `dirty_all` also removes the
                         outputs on disk.
        "cancel"       — stop the cook that runs now.
        "render_setup" — several cameras, render settings or quality levels
                         of one shot, rendered `parallel` jobs at a time. Give
                         the ROP at `path` (Karma or USD Render ROP in /out or
                         /stage, Mantra, OpenGL) and `variants`: one object per
                         render, `variant` names it (and its output folder),
                         every other key is the name of a parameter on the ROP:
                         [{"variant": "front", "camera": "/cameras/front"},
                          {"variant": "top", "camera": "/cameras/top",
                           "resolution": [960, 540]}]
                         The ROP is not changed: a copy next to it reads the
                         values from the work items, each variant writes to
                         `output_root`/<variant>/. `frame_range` is
                         [start, end] or [start, end, step]; without it the
                         ROP's own range. Read the `pdg` rules topic first.

    Returns JSON. A failed item holds its log path: read it before you change
    the network. "render_setup" names the keys that matched no parameter.
    """
    return call_json("pdg", {"path": path, "mode": mode, "state": state,
                             "dirty_all": dirty_all, "variants": variants,
                             "parallel": parallel, "frame_range": frame_range,
                             "name": name, "parent_path": parent_path,
                             "output_root": output_root,
                             "frames_per_batch": frames_per_batch},
                     timeout=300.0)
