"""select — which nodes are selected."""
from typing import List, Union

from ..connection import call_json


def tool(paths: Union[str, List[str]] = None, show: bool = False,
         display: bool = False) -> str:
    """Read the node selection, set it, or show the work on screen.

    Use it to see what the person works on before you change the scene, and to
    put your own result in front of them.

    paths: nothing reads the selection. One path or a list of paths replaces
    it. An empty list clears it.

    show: also open the network of the first node in the network editor, frame
    the nodes there, point the viewer at that network and frame what it draws.
    Houdini panes never follow work done through tools: without show, a person
    watching the screen sees an empty network and an old picture. Call it at the
    start of each stage on the network you build in, and after each stage on
    its result.

    display: with show, also move the display flag to the first node, so the
    viewer draws its result. It changes what the network outputs: move it back
    when the stage is done if the chain needs the old flag.

    Returns JSON with the selected paths, or with what is shown.
    """
    params = {"paths": paths}
    if show:
        params.update(show=True, display=display)
    return call_json("select", params)
