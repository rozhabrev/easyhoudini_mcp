"""Make a picture of the scene, and say what the window shows.

Without a GUI there is no viewport. Then an OpenGL ROP draws the same picture,
so the same call answers in hython and in a Houdini with a window.
"""
import base64

import hou

from . import unknown_mode
from ..handlers import offscreen, sheets, timelapse, viewport

MUTATES = True  # a capture moves the view, and puts it back after

MODES = ("viewport", "quad", "camera", "flipbook", "sheet", "movie", "timelapse")

# The longest side of a picture that goes back to the agent. The model scales a
# larger picture down anyway, and the message must stay small.
INLINE_SIDE = 1280
INLINE_QUALITY = 80
# More pictures than this in one result go back as paths only.
MAX_INLINE = 12


def run(mode="viewport", node=None, output=None, camera=None, direction=None,
        shading=None, renderer=None, frame=None, target=None, look_from=None,
        radius=None, fill=0.9, frame_range=None, frames=None,
        resolution=None, azimuth=None, elevation=None, start=None, step=1,
        count=12, columns=None, tile_width=320, background=96, reference=None,
        color_by=None, color_range=None, fps=24, contour=None, slab=None,
        vectors=None, settle=None, enabled=None, folder=None):
    if mode not in MODES:
        raise unknown_mode(mode, MODES)
    if mode == "timelapse":
        return timelapse.configure(enabled=enabled, folder=folder, camera=camera)
    if mode in ("sheet", "movie"):
        # An OpenGL ROP draws these with or without a window, so the call is
        # the same in both.
        if not node:
            raise ValueError(f"mode '{mode}' needs `node`.")
        shared = dict(node_path=node, background=background, azimuth=azimuth,
                      elevation=elevation, fill=fill, color_by=color_by,
                      color_range=color_range, contour=contour, slab=slab,
                      vectors=vectors, output=output)
        if mode == "sheet":
            return _inline(sheets.sheet(frames=frames, start=start, step=step, count=count,
                                columns=columns, tile_width=tile_width,
                                reference=reference, **shared))
        return sheets.movie(frames=_span(frames, frame_range), fps=fps,
                            width=(resolution or [640])[0], **shared)
    if not hou.isUIAvailable():
        # No window, so no viewport. An OpenGL ROP draws without one, and the
        # arguments mean the same thing, so the caller writes the same call.
        result = offscreen.capture(
            node_path=node, output=output, frames=_span(frames, frame_range),
            resolution=resolution, camera=camera, direction=direction or "persp",
            target=target, look_from=look_from, radius=radius, fill=fill,
            shading=shading, azimuth=azimuth, elevation=elevation)
        result = {**result, "window_state": _state()}
        return result if mode == "flipbook" else _inline(result)

    if mode == "flipbook" and not (frames or frame_range):
        frame_range = list(hou.playbar.frameRange())
    if mode == "camera" and not camera:
        raise ValueError("mode 'camera' needs the path of a camera node.")
    return _with_state(mode, viewport.capture(
        mode=mode, node=node, output=output, camera=camera,
        direction=direction, shading=shading, renderer=renderer, frame=frame,
        target=target, look_from=look_from, radius=radius, fill=fill,
        frame_range=frame_range, frames=frames, resolution=resolution,
        azimuth=azimuth, elevation=elevation, settle=settle))


def _with_state(mode, capture):
    """A viewport capture waits in the event loop (see server._step), so the
    state of the window is read when it ends."""
    result = yield from capture
    result = {**result, "window_state": _state()}
    return result if mode == "flipbook" else _inline(result)


def _inline(result):
    """Put each picture into the result as a small JPEG.

    The agent often runs on another machine than Houdini, and there the path
    of the file is no use: the bridge gives the model these bytes instead.
    """
    images = result.get("images") or []
    paths = [image["filepath"] for image in images if image.get("filepath")] or \
            [result.get("filepath") or result.get("path")]
    paths = [path for path in paths if path]
    result["inline"] = [{"path": path, "jpeg": _jpeg(path)} for path in paths[:MAX_INLINE]]
    if len(paths) > MAX_INLINE:
        result["not_inline"] = paths[MAX_INLINE:]
    return result


def _jpeg(path):
    """The picture at `path` as base64 JPEG, no larger than INLINE_SIDE."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
    from PySide6.QtGui import QImage

    image = QImage(path)
    if image.isNull():
        raise RuntimeError(f"Qt cannot read the picture {path}.")
    if max(image.width(), image.height()) > INLINE_SIDE:
        image = image.scaled(INLINE_SIDE, INLINE_SIDE, Qt.KeepAspectRatio,
                             Qt.SmoothTransformation)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.WriteOnly)
    if not image.save(buffer, "JPG", INLINE_QUALITY):
        raise RuntimeError(f"Qt cannot write {path} as JPEG.")
    return base64.b64encode(bytes(data)).decode("ascii")


def _span(frames, frame_range):
    """The frames to draw: a list, a number, or the range between two numbers."""
    if frames is not None:
        return frames
    if frame_range:
        return {"start": frame_range[0], "end": frame_range[-1]}
    return None


def _state():
    """What the session shows now: frame, selection, the network in front, and
    which nodes carry the display, the render and the template flag."""
    state = {"frame": hou.frame(), "hip_file": hou.hipFile.path(),
             "selected": [node.path() for node in hou.selectedNodes()],
             "ui_available": hou.isUIAvailable()}
    if not hou.isUIAvailable():
        return state
    editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    state["network"] = editor.pwd().path() if editor else None
    try:
        state["viewport"] = viewport.get_viewport_info()
    except Exception as error:
        state["viewport"] = f"unavailable: {error}"
    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    state["flags"] = _flags(viewer.pwd() if viewer else
                            (editor.pwd() if editor else None))
    return state


def _flags(network):
    """Which node the picture actually shows.

    A picture that does not change after an edit is almost always a display
    flag on another node, so the answer names the flagged nodes every time.
    """
    if not network:
        return None
    found = {"network": network.path()}
    for name, read in (("display", "displayNode"), ("render", "renderNode")):
        try:
            node = getattr(network, read)()
        except AttributeError:
            continue
        found[name] = node.path() if node else None
    # At object level no single node carries the flag: each object carries its
    # own, and an object that is off is why the picture is empty.
    if "display" not in found:
        found["displayed"] = _flagged(network, "isDisplayFlagSet")
    found["template"] = _flagged(network, "isTemplateFlagSet")
    return found


def _flagged(network, test):
    """The children of a network whose flag is on."""
    on = []
    for child in network.children():
        try:
            if getattr(child, test)():
                on.append(child.path())
        except AttributeError:
            continue
    return on
