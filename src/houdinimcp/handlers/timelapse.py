"""Timelapse of an agent session: two frames after each change.

A screen recording of an hour of work is heavy and almost static. A viewer
wants to see the scene grow step by step. So after each call that changes the
scene, when the window stops changing:

1. The panes follow the work (follow.py): the network editor goes to the node
   that the call changed, the display flag moves to the new end of the chain,
   and the viewer shows that network.
2. The Houdini main window goes into a numbered JPEG in screen/.
3. A flipbook of one frame draws the whole scene from one camera that does not
   move, into view/: the same place frame after frame, so the scene grows in
   it. The camera only backs off when the scene outgrows the frame. A camera
   given to capture mode "timelapse" replaces it.

The files that a render wrote are copied next to them:

    <project>/timelapse/
        screen/   0001_node_edit.jpg, ...
        view/     0001_node_edit.jpg, ...
        renders/  0001_beauty.0001.exr, ...

Only the Houdini main window goes into the frame, never the desktop: the user
often works on the same machine, and a picture of the desktop records their
messenger. MPlay and the other floating windows stay out too.

On by default in a Houdini with a window. HOUDINIMCP_TIMELAPSE=0 turns it off
at start, and capture mode "timelapse" turns it on or off while Houdini runs.
"""
import contextlib
import os
import re
import shutil
import time

import hou

from . import follow, viewport

# Quiet time after the last change before the frame. A node_edit is often
# followed by a parm_set and a connect within a second: one frame of the
# finished step reads better than three of a half-built one, and the viewport
# needs a moment to draw.
DELAY_MS = 1500
# A long series of changes without a pause still gets a frame this often.
MAX_GAP_S = 10.0
# Time for the panes to draw after they follow the work, before the frame.
REDRAW_MS = 400
# The width of a frame of the view track.
VIEW_WIDTH = 1280
# The direction from the middle of the scene to the eye of the view track.
VIEW_DIRECTION = (1.0, 0.55, 1.0)
JPEG_QUALITY = 88
# A render of a long sequence copies no more files than this in one call.
MAX_RENDER_COPIES = 2000
# Tools that change the scene only in a way that a frame does not show, or that
# make pictures themselves.
SKIP = frozenset({"capture", "select", "session", "docs"})
# The parameters that hold the picture a ROP writes. The first one that a node
# has is the one it writes.
IMAGE_PARMS = ("picture", "vm_picture", "copoutput", "outputimage", "filename")

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

# importlib.reload keeps the module namespace, so the counter and the timer
# live through a plugin reload.
try:
    STATE  # noqa: B018
except NameError:
    STATE = {"enabled": None, "folder": None, "timer": None, "pending_since": None,
             "pending_label": "", "pending_node": None, "last_node": None,
             "last_shot": None, "shots": 0, "renders": 0, "views": 0,
             "camera": None, "view_box": None, "followed": None, "last_error": None}


def is_enabled() -> bool:
    if STATE["enabled"] is None:
        value = os.environ.get("HOUDINIMCP_TIMELAPSE", "1").strip().lower()
        STATE["enabled"] = value not in ("", "0", "false", "off", "no")
    return bool(STATE["enabled"]) and hou.isUIAvailable()


def root():
    """The timelapse folder. None while the scene is not saved.

    An untitled scene has $HIP in the start directory of Houdini, and frames
    there are lost. A hip file in a `hip` or `scenes` folder puts the
    timelapse at the root of the project, next to that folder.
    """
    explicit = STATE["folder"] or os.environ.get("HOUDINIMCP_TIMELAPSE_DIR")
    if explicit:
        return hou.text.expandString(explicit)
    hip_file = hou.hipFile.path()
    if not hip_file or hou.hipFile.isNewFile() or "untitled" in os.path.basename(hip_file):
        return None
    folder = os.path.dirname(hip_file)
    if os.path.basename(folder).lower() in ("hip", "scenes", "scene"):
        folder = os.path.dirname(folder)
    return os.path.join(folder, "timelapse")


def next_index(folder) -> int:
    highest = 0
    with contextlib.suppress(OSError):
        for name in os.listdir(folder):
            head = name.split("_", 1)[0]
            if head.isdigit():
                highest = max(highest, int(head))
    return highest + 1


def file_name(index, label, extension) -> str:
    label = _UNSAFE.sub("-", label or "").strip("-")[:60]
    return f"{index:04d}" + (f"_{label}" if label else "") + extension


# Capture


def _looks_blank(image, rect) -> bool:
    """True when a region of the grab is black, as a GL pane can be on some
    drivers."""
    if rect.width() < 8 or rect.height() < 8:
        return False
    for x in (0.25, 0.5, 0.75):
        for y in (0.25, 0.5, 0.75):
            colour = image.pixelColor(rect.x() + int(rect.width() * x),
                                      rect.y() + int(rect.height() * y))
            if colour.red() + colour.green() + colour.blue() > 6:
                return False
    return True


def grab_main_window():
    """The Houdini main window as a QImage, or None when it is not on screen.

    QWidget.grab draws the window itself, so a window on top of Houdini is
    never in the frame. When the viewport comes back black (the GL surface was
    not read back), the area of the screen under the window is read instead,
    and only while Houdini is the active window, so that those pixels are still
    the pixels of Houdini.
    """
    from PySide6 import QtCore, QtGui, QtWidgets

    window = hou.qt.mainWindow()
    if window is None or window.isMinimized() or not window.isVisible():
        return None
    image = window.grab().toImage()

    viewer_rect = None
    with contextlib.suppress(Exception):
        viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if viewer is not None and hasattr(viewer, "qtScreenGeometry"):
            screen_rect = viewer.qtScreenGeometry()
            viewer_rect = QtCore.QRect(window.mapFromGlobal(screen_rect.topLeft()),
                                       screen_rect.size())
    if viewer_rect is None or not _looks_blank(image, viewer_rect):
        return image
    if QtWidgets.QApplication.activeWindow() is not window:
        return image
    top_left = window.mapToGlobal(QtCore.QPoint(0, 0))
    screen = QtGui.QGuiApplication.screenAt(top_left) or QtGui.QGuiApplication.primaryScreen()
    origin = screen.geometry().topLeft()
    return screen.grabWindow(0, top_left.x() - origin.x(), top_left.y() - origin.y(),
                             window.width(), window.height()).toImage()


def frame_index():
    """One number for the frames of both tracks, so that they pair up."""
    folder = root()
    if folder is None:
        return None
    return max(next_index(os.path.join(folder, track)) for track in ("screen", "view"))


def take_frame(label="", index=None):
    """Save one frame of the Houdini window now. Returns its path, or None and
    the reason in STATE["last_error"]."""
    folder = root()
    if folder is None:
        STATE["last_error"] = "the scene is not saved, so there is no project folder"
        return None
    folder = os.path.join(folder, "screen")
    os.makedirs(folder, exist_ok=True)
    image = grab_main_window()
    if image is None or image.isNull():
        STATE["last_error"] = "the Houdini window is minimized or hidden"
        return None
    path = os.path.join(folder, file_name(index or next_index(folder), label, ".jpg"))
    if not image.save(path, "JPG", JPEG_QUALITY):
        STATE["last_error"] = f"could not write {path}"
        return None
    STATE.update(shots=STATE["shots"] + 1, last_shot=path, last_error=None)
    return path


# The view track


def _work_network():
    """The top network of the scene the agent builds: /stage when the last
    work is under it, or when /obj shows nothing; else /obj."""
    node = STATE["last_node"]
    with contextlib.suppress(hou.ObjectWasDeleted, AttributeError):
        top = node.path().split("/")[1] if node is not None else ""
        if top in ("stage", "obj"):
            return hou.node("/" + top)
    stage = hou.node("/stage")
    if stage is not None and stage.displayNode() is not None:
        return stage
    return hou.node("/obj")


def _aim_view(port, network):
    """Point the view track at the whole scene from VIEW_DIRECTION. The frame
    holds still and backs off only when the scene outgrows it."""
    box = follow.network_box(network)
    if box is None:
        return False
    if follow.outgrown(box, STATE["view_box"]):
        # Room for the scene to grow before the camera must move again.
        STATE["view_box"] = follow.grown(box, 0.75)
    held = STATE["view_box"]
    centre = held.center()
    radius = max(held.sizevec().length(), 1e-3)
    direction = hou.Vector3(VIEW_DIRECTION).normalized()
    port.changeType(hou.geometryViewportType.Perspective)
    viewport.aim(port, target=list(centre), look_from=list(centre + direction * radius * 2.0))
    port.frameBoundingBox(held)
    return True


def _look_through(port, network):
    """Look through the timelapse camera. False when the viewer does not take
    it now: a USD camera needs a turn of the event loop the first time."""
    camera = STATE["camera"]
    with contextlib.suppress(hou.Error, TypeError):
        port.setCamera(camera)
        if network.childTypeCategory() == hou.lopNodeTypeCategory():
            return port.cameraPath() == camera
        return port.camera() is not None
    return False


def take_view(label="", index=None):
    """Draw the whole scene from the timelapse camera into view/ with a
    flipbook of one frame: a quick OpenGL picture, not a render. The viewer
    shows the top network for the picture and goes back after, with its
    camera, renderer and shading."""
    folder = root()
    viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    network = _work_network()
    if folder is None or viewer is None or network is None:
        return None
    shown = network.displayNode()
    if shown is None or shown.needsToCook():
        # A flipbook cooks what it draws, and a heavy cook inside a flipbook
        # quit Houdini once. The view takes only a scene that is cooked.
        return None
    folder = os.path.join(folder, "view")
    path = os.path.join(folder, file_name(index or next_index(folder), label, ".jpg"))
    before = viewer.pwd()
    try:
        if before != network:
            viewer.setPwd(network)
        port = viewer.curViewport()
        with viewport.kept_look(viewer), viewport.kept_view(port):
            if network.childTypeCategory() == hou.lopNodeTypeCategory():
                viewer.setShowCameras(False)
                if "gl" not in (viewer.currentHydraRenderer() or "").lower():
                    # Karma in the viewer starts from noise: the GL picture is
                    # the quick one.
                    with contextlib.suppress(ValueError):
                        viewport.set_viewport_renderer("Houdini GL")
            if not (STATE["camera"] and _look_through(port, network)):
                if not _aim_view(port, network):
                    return None  # nothing drawn yet
            steps = viewport.write_image(viewer, port, path, [VIEW_WIDTH])
            try:
                next(steps)
                return None  # a picture that waits for the event loop: skip it
            except StopIteration:
                pass
    except RuntimeError as error:
        # An empty picture: the scene draws nothing yet. Not an error of the session.
        STATE["last_error"] = f"view: {error}"
        return None
    finally:
        with contextlib.suppress(hou.Error):
            if viewer.pwd() != before:
                viewer.setPwd(before)
    STATE["views"] += 1
    return path


def _shoot(label):
    if not is_enabled():
        return
    try:
        index = frame_index()
        take_frame(label, index)
    except Exception as error:
        STATE["last_error"] = f"{type(error).__name__}: {error}"
        return
    try:
        take_view(label, index)
    except Exception as error:
        STATE["last_error"] = f"view: {type(error).__name__}: {error}"


def _fire():
    from PySide6 import QtCore

    label, node = STATE["pending_label"], STATE["pending_node"]
    STATE.update(pending_since=None, pending_label="", pending_node=None)
    if not is_enabled():
        return
    if node is not None:
        STATE["last_node"] = node
    STATE["followed"] = follow.follow(STATE["last_node"])
    # The panes draw in the event loop: give them a moment before the frame.
    QtCore.QTimer.singleShot(REDRAW_MS, lambda: _shoot(label))


def schedule(label):
    """Take a frame when the changes stop for a moment. Runs on the main thread."""
    from PySide6 import QtCore

    timer = STATE["timer"]
    if timer is None:
        timer = QtCore.QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(_fire)
        STATE["timer"] = timer
    now = time.time()
    if STATE["pending_since"] is None:
        STATE["pending_since"] = now
    STATE["pending_label"] = label
    if timer.isActive() and now - STATE["pending_since"] >= MAX_GAP_S:
        return  # a frame is due soon: do not push it back again
    timer.start(DELAY_MS)


# Renders


def _frames(node, frame_range):
    if frame_range and len(frame_range) >= 2:
        start, end = float(frame_range[0]), float(frame_range[1])
        step = 1.0
    else:
        trange, f1, f2, f3 = (node.parm(name) for name in ("trange", "f1", "f2", "f3"))
        if trange is None or not trange.eval() or f1 is None or f2 is None:
            return [hou.frame()]
        start, end = f1.eval(), f2.eval()
        step = (f3.eval() if f3 is not None else 0) or 1.0
    frames, frame = [], start
    while frame <= end + 1e-6 and len(frames) < MAX_RENDER_COPIES:
        frames.append(frame)
        frame += step
    return frames


def render_files(path, frame_range):
    """Every file that the ROP at `path` writes over the frames it rendered."""
    node = hou.node(path or "")
    if node is None:
        return []
    parm = next((node.parm(name) for name in IMAGE_PARMS if node.parm(name)), None)
    if parm is None:
        return []
    files = []
    for frame in _frames(node, frame_range):
        with contextlib.suppress(Exception):
            value = parm.evalAtFrame(frame)
            if value and not value.startswith(("ip", "md", "op:")):
                files.append(os.path.normpath(value))
    return list(dict.fromkeys(files))


def copy_render(path, frame_range, started):
    """Copy the files that a render wrote just now into timelapse/renders."""
    folder = root()
    if folder is None:
        return []
    fresh = [file for file in render_files(path, frame_range)
             if os.path.isfile(file) and os.path.getmtime(file) >= started - 1]
    if not fresh:
        return []
    folder = os.path.join(folder, "renders")
    os.makedirs(folder, exist_ok=True)
    index = next_index(folder)
    copied = []
    for file in fresh:
        stem, extension = os.path.splitext(os.path.basename(file))
        target = os.path.join(folder, file_name(index, stem, extension))
        shutil.copy2(file, target)
        copied.append(target)
    STATE["renders"] += len(copied)
    return copied


# The hook in tools.dispatch


def before(command):
    """Called before each call of a tool with MUTATES. An execute names no
    node in its params, so the nodes before it tell what it made."""
    if command == "execute" and is_enabled():
        return follow.nodes_now()
    return None


def after(command, params, started, result=None, mark=None):
    """Called after each call of a tool with MUTATES that did not fail."""
    if not is_enabled():
        return
    # select with show turns the panes to the work: that is what a frame is for.
    if command in SKIP and not (command == "select" and params.get("show")):
        return
    if command == "render" and params.get("mode", "start") == "start":
        try:
            copy_render(params.get("path"), params.get("frame_range"), started)
        except Exception as error:
            STATE["last_error"] = f"render copy: {type(error).__name__}: {error}"
    if command not in SKIP and command != "batch":
        # A batch names its nodes in the calls inside it, and each of those
        # comes here on its own.
        try:
            node = follow.touched(command, params, result, mark)
        except Exception as error:
            node = None
            STATE["last_error"] = f"follow: {type(error).__name__}: {error}"
        if node is not None:
            STATE["pending_node"] = node
    mode = params.get("mode")
    schedule(f"{command}-{mode}" if isinstance(mode, str) else command)


def configure(enabled=None, folder=None, camera=None):
    """Turn the timelapse on or off, move it, or set the camera of the view
    track ("" for the camera that frames the whole scene), and take a frame
    now."""
    if enabled is not None:
        STATE["enabled"] = bool(enabled)
    if folder is not None:
        STATE["folder"] = folder.strip() or None
    if camera is not None:
        STATE["camera"] = camera.strip() or None
        STATE["view_box"] = None
    shot = view = None
    if is_enabled() and root() is not None:
        index = frame_index()
        shot = take_frame("snapshot", index)
        with contextlib.suppress(Exception):
            view = take_view("snapshot", index)
    folder = root()
    return {"enabled": is_enabled(), "folder": folder, "camera": STATE["camera"],
            "frames_this_session": STATE["shots"],
            "views_this_session": STATE["views"],
            "renders_copied_this_session": STATE["renders"],
            "last_frame": shot or STATE["last_shot"], "last_view": view,
            "followed": STATE["followed"],
            "last_error": STATE["last_error"],
            "note": None if folder else "Save the scene: the frames go next to the hip file."}
