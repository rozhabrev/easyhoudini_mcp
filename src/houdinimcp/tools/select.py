"""Read or set the node selection."""
from . import as_list
from ..handlers import context

MUTATES = True


def run(paths=None, show=False, display=False):
    """No paths reads the selection. Paths set it. show also opens their
    network in the network editor and the viewer, and frames them."""
    if paths is None:
        return context.get_selection()
    if show and as_list(paths):
        return context.show(as_list(paths), display=bool(display))
    return context.set_selection(as_list(paths))
