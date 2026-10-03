"""capture — look at the scene: a picture of the viewport, and the window state."""
import base64
import json
from typing import Dict, List, Union

from mcp.server.mcpserver import Image

from ..connection import call

def tool(mode: str = "viewport", node: str = None, output: str = None,
         camera: str = None, direction: str = None, shading: str = None,
         renderer: str = None, frame: str = None,
         target: List[float] = None, look_from: List[float] = None,
         radius: float = None, fill: float = 0.9,
         frame_range: List[float] = None,
         frames: Union[float, List[float], Dict[str, float]] = None,
         resolution: List[int] = None, azimuth: float = None,
         elevation: float = None, start: float = None, step: float = 1,
         count: int = 12, columns: int = None, tile_width: int = 320,
         background: int = 96, reference: str = None, color_by: str = None,
         color_range: List[float] = None, fps: float = 24, contour: float = None,
         slab: List[Union[str, float]] = None,
         vectors: float = None, settle: float = None, enabled: bool = None,
         folder: str = None) -> list[Image | str]:
    """Make a picture of the scene and look at it.

    Use it to confirm your own work: numbers in a node do not tell you that the
    result looks wrong. Use it before you report that a task is done.

    Do not use it for a final picture: render does that through a ROP.

    The view goes back to where the user left it when the picture is written.
    Nothing here changes the scene for good.

    mode:
        "viewport" — the viewport as it is now.
        "quad"     — four pictures: top, front, right and perspective.
        "camera"   — through the camera node at `camera`.
        "flipbook" — a sequence over `frame_range` [start, end]. Returns the
                     path of the files, not a picture.
        "sheet"    — `node` at many frames on one picture, a tile for each
                     frame with its number, all from one camera that does not
                     move. Frames: `frames`, or `count` frames from `start`
                     (the current frame) at `step` (1). A step over 2 hides
                     movement and gives a warning: look at a short range at
                     step 1. `reference` is a picture to put first, to
                     compare. `columns`, `tile_width` set the grid. The
                     frames cook in order, forward, and the result gives
                     the cook seconds of each one.
        "movie"    — `node` over `frames` or `frame_range` (the playbar
                     range) as an MP4 at `fps`, `resolution` [width] wide.
                     Returns the path; open it in a player.
        "timelapse" — the record of this session. After each call that
                     changes the scene, the panes go to the node the call
                     changed: the network editor opens its network, the
                     display flag moves to the new end of the chain the
                     viewer draws, and the viewer shows that network. Then a
                     frame of the Houdini main window goes to
                     <project>/timelapse/screen/, and a quick OpenGL picture
                     of the whole scene from one still camera goes to
                     <project>/timelapse/view/. The files that render writes
                     go to <project>/timelapse/renders/. Other windows, MPlay
                     too, stay out of the frame. It is on by default and
                     needs a saved scene. `enabled` turns it on or off,
                     `folder` moves it ("" for the default), `camera` gives
                     the view track a camera node or USD camera prim ("" for
                     the still camera that frames the whole scene). The call
                     takes a frame now and returns the state.
        Both draw with an OpenGL ROP, with or without a window, over a flat
        grey `background` (0-255, 96 by default: smoke reads best on mid
        grey). `color_by` colours the points by an attribute, blue at the low
        end of `color_range` [low, high] and red at the high end; a vector
        attribute uses its length. To see where a point attribute lives, use
        "sheet" with one frame and these:
            contour — a step: colour by the fraction of the value over the
                      step. The lines of equal value show the shape of a
                      field, for example the shells of a distance field.
            slab    — [axis, thickness], for example ["z", 0.1]: only the
                      points in a thin cut through the middle, so the inside
                      of a solid cloud shows.
            vectors — a scale: a line along the `color_by` vector from up to
                      about 3000 points. An empty result is an error.

    A Houdini with no window has no viewport, and there an OpenGL ROP draws the
    same picture from the same arguments over a grey background. It runs in a
    new hython, so the scene gets no camera and no ROP.


    There is no picture of the network editor: every Houdini pane is a native
    GL drawable, and Qt draws nothing into it. Read the graph with node_inspect.

    node: the node to look at. Its display flag is set for the picture and the
    node that held the flag gets it back after. When the viewer shows another
    network, it shows the network of the node for the picture and goes back
    after. Without `frame` the view also frames that node.

    frames: one frame, a list, or {"start": 1, "end": 10, "step": 2}: one
    picture for each, and the playbar goes back after. A picture that holds
    only the background is an error, not a result.

    Aim the view with any of these:
        frame      — "selection", "all", or the path of a node: frame the view
                     on the box of what that node cooked.
        fill       — how much of the picture the framed thing takes. 0.9 leaves
                     air around it; 1.0 fills the frame.
        target     — [x, y, z] that the view turns around.
        look_from  — [x, y, z] that the view looks from.
        radius     — the distance between the two.
        direction  — "top", "front", "left", "right", "back", "bottom",
                     "persp".
        azimuth    — turn the view around what it frames, in degrees around
                     the up axis; with `elevation`, the degrees above the
                     ground. 0 and 0 look from the front; azimuth 45 and
                     elevation 30 give a three-quarter view. Nothing is added
                     to the scene.
        camera     — look through this camera node.
        shading    — "smooth", "smooth_wire", "flat", "wireframe".
        renderer   — the Hydra renderer of a viewer on a LOP network, for
                     example "Karma CPU". An unknown name lists the ones
                     available. `camera` can then be a USD camera prim.
        settle     — the seconds that a renderer such as Karma draws before
                     each picture. Karma starts from noise, and a picture
                     taken at once is blank. 20 to 30 gives a clean frame.
                     With `frames`, or in mode "flipbook", it renders a
                     sequence through the viewport, one frame at a time,
                     with no husk and no render license, and gives the
                     seconds of each frame. The renderer, the
                     shading and the camera guides go back after.

    output: where to write the file. Without it, Houdini writes to a temporary
    file. resolution is [width, height]; the height follows the shape of
    the viewport, so the picture is not stretched.

    Returns the picture, plus JSON with the state of the window: the frame, the
    open file, the selection, the network in front, and which nodes carry the
    display, the render and the template flag. A picture that does not change
    after an edit is almost always a display flag on another node.

    Houdini without a GUI has no viewport: then the result says so and names
    the next action.
    """
    result = call("capture", {"mode": mode, "node": node, "output": output,
                              "camera": camera, "direction": direction,
                              "shading": shading, "renderer": renderer,
                              "frame": frame, "target": target,
                              "look_from": look_from, "radius": radius,
                              "fill": fill, "frame_range": frame_range,
                              "frames": frames, "resolution": resolution,
                              "azimuth": azimuth, "elevation": elevation,
                              "start": start, "step": step, "count": count,
                              "columns": columns, "tile_width": tile_width,
                              "background": background, "reference": reference,
                              "color_by": color_by, "color_range": color_range,
                              "fps": fps, "contour": contour, "slab": slab,
                              "vectors": vectors, "settle": settle,
                              "enabled": enabled, "folder": folder},
                  timeout=300.0 + (settle or 0) * 1.5 * _count(frames))

    return pictures(result) + [json.dumps(result, indent=2, default=str)]


def pictures(result) -> list:
    """The pictures of a capture result, taken out of its JSON.

    The plugin sends each picture as a small JPEG: Houdini often runs on
    another machine, where the path means nothing to this one.
    """
    return [Image(data=base64.b64decode(item["jpeg"]), format="jpeg")
            for item in result.pop("inline", None) or []]


def _count(frames) -> int:
    """How many pictures `frames` asks for, to size the wait."""
    if isinstance(frames, list):
        return len(frames)
    if isinstance(frames, dict):
        step = abs(float(frames.get("step") or 1))
        return int(abs(float(frames.get("end", frames["start"])) - float(frames["start"]))
                   / step) + 1
    return 1
