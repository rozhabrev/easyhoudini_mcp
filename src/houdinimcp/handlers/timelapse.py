"""Timelapse of an agent session: a frame of the Houdini window after each change.

A screen recording of an hour of work is heavy and almost static. A viewer
wants to see the scene grow step by step. So after each call that changes the
scene, when the window stops changing, the Houdini main window goes into a
numbered JPEG, and the files that a render wrote are copied next to them:

    <project>/timelapse/
        screen/   0001_node_edit.jpg, ...
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

# Quiet time after the last change before the frame. A node_edit is often
# followed by a parm_set and a connect within a second: one frame of the
# finished step reads better than three of a half-built one, and the viewport
# needs a moment to draw.
DELAY_MS = 1500
# A long series of changes without a pause still gets a frame this often.
MAX_GAP_S = 10.0
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
             "pending_label": "", "last_shot": None, "shots": 0, "renders": 0,
             "last_error": None}


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


def take_frame(label=""):
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
    path = os.path.join(folder, file_name(next_index(folder), label, ".jpg"))
    if not image.save(path, "JPG", JPEG_QUALITY):
        STATE["last_error"] = f"could not write {path}"
        return None
    STATE.update(shots=STATE["shots"] + 1, last_shot=path, last_error=None)
    return path


def _fire():
    label = STATE["pending_label"]
    STATE.update(pending_since=None, pending_label="")
    if not is_enabled():
        return
    try:
        take_frame(label)
    except Exception as error:
        STATE["last_error"] = f"{type(error).__name__}: {error}"


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


def after(command, params, started):
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
    mode = params.get("mode")
    schedule(f"{command}-{mode}" if isinstance(mode, str) else command)


def configure(enabled=None, folder=None):
    """Turn the timelapse on or off, or move it, and take a frame now."""
    if enabled is not None:
        STATE["enabled"] = bool(enabled)
    if folder is not None:
        STATE["folder"] = folder.strip() or None
    shot = take_frame("snapshot") if is_enabled() else None
    folder = root()
    return {"enabled": is_enabled(), "folder": folder,
            "frames_this_session": STATE["shots"],
            "renders_copied_this_session": STATE["renders"],
            "last_frame": shot or STATE["last_shot"],
            "last_error": STATE["last_error"],
            "note": None if folder else "Save the scene: the frames go next to the hip file."}
