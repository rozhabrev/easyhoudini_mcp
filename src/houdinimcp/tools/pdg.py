"""TOP networks: cook them, read their state, dirty or cancel them."""
from . import unknown_mode
from ..handlers import pdg as handler

MUTATES = True

MODES = ("cook", "status", "workitems", "dirty", "cancel", "render_setup")


def run(path, mode="status", state=None, dirty_all=False, variants=None,
        parallel=2, frame_range=None, name=None, parent_path="/obj",
        output_root="$HIP/render/variants", frames_per_batch=1):
    if mode == "render_setup":
        return handler.render_setup(path, variants, parallel, frame_range, name,
                                    parent_path, output_root, frames_per_batch)
    if mode == "cook":
        return handler.pdg_cook(path)
    if mode == "status":
        return handler.pdg_status(path)
    if mode == "workitems":
        return handler.pdg_workitems(path, state)
    if mode == "dirty":
        return handler.pdg_dirty(path, dirty_all)
    if mode == "cancel":
        return handler.pdg_cancel(path)
    raise unknown_mode(mode, MODES)
