import os
import time
from unittest import mock

from PySide6.QtGui import QColor, QImage


def saved(hou, path):
    hou.hipFile.path.return_value = path
    hou.hipFile.isNewFile.return_value = False


def test_no_folder_while_the_scene_is_not_saved(timelapse):
    assert timelapse.root() is None
    assert timelapse.take_frame() is None
    assert "not saved" in timelapse.STATE["last_error"]


def test_folder_is_at_the_project_root(timelapse, hou, tmp_path):
    saved(hou, str(tmp_path / "proj" / "hip" / "tower_s012.hip"))
    assert timelapse.root() == str(tmp_path / "proj" / "timelapse")
    saved(hou, str(tmp_path / "loose" / "tower.hip"))
    assert timelapse.root() == str(tmp_path / "loose" / "timelapse")
    timelapse.STATE["folder"] = str(tmp_path / "elsewhere")
    assert timelapse.root() == str(tmp_path / "elsewhere")


def test_file_names_count_on_from_the_folder(timelapse, tmp_path):
    assert timelapse.next_index(str(tmp_path)) == 1
    (tmp_path / "0007_node_edit.jpg").write_bytes(b"")
    (tmp_path / "notes.txt").write_bytes(b"")
    assert timelapse.next_index(str(tmp_path)) == 8
    assert timelapse.file_name(8, "parm_set/set x", ".jpg") == "0008_parm_set-set-x.jpg"
    assert timelapse.file_name(9, "", ".jpg") == "0009.jpg"


def test_off_without_a_window_and_by_environment(timelapse, hou, monkeypatch):
    hou.isUIAvailable.return_value = False
    assert not timelapse.is_enabled()
    hou.isUIAvailable.return_value = True
    timelapse.STATE["enabled"] = None
    monkeypatch.setenv("HOUDINIMCP_TIMELAPSE", "0")
    assert not timelapse.is_enabled()
    timelapse.STATE["enabled"] = None
    monkeypatch.delenv("HOUDINIMCP_TIMELAPSE")
    assert timelapse.is_enabled()  # on by default


def test_after_schedules_a_frame_only_for_changes(timelapse, monkeypatch):
    labels = []
    monkeypatch.setattr(timelapse, "schedule", labels.append)
    for command in ("capture", "select", "session", "docs"):
        timelapse.after(command, {}, time.time())
    timelapse.after("node_edit", {"mode": "create"}, time.time())
    timelapse.after("execute", {"code": "x"}, time.time())
    assert labels == ["node_edit-create", "execute"]
    timelapse.STATE["enabled"] = False
    timelapse.after("node_edit", {}, time.time())
    assert labels == ["node_edit-create", "execute"]


def test_a_frame_is_the_houdini_window(timelapse, hou, tmp_path, monkeypatch, qt_app):
    saved(hou, str(tmp_path / "proj" / "hip" / "t.hip"))
    image = QImage(64, 32, QImage.Format_RGB32)
    image.fill(QColor("red"))
    monkeypatch.setattr(timelapse, "grab_main_window", lambda: image)
    first = timelapse.take_frame("node_edit")
    second = timelapse.take_frame("parm_set")
    folder = tmp_path / "proj" / "timelapse" / "screen"
    assert first == str(folder / "0001_node_edit.jpg")
    assert second == str(folder / "0002_parm_set.jpg")
    assert QImage(second).width() == 64
    assert timelapse.STATE["shots"] == 2


def test_a_hidden_window_gives_no_frame(timelapse, hou, tmp_path, monkeypatch):
    saved(hou, str(tmp_path / "t.hip"))
    monkeypatch.setattr(timelapse, "grab_main_window", lambda: None)
    assert timelapse.take_frame() is None
    assert "minimized" in timelapse.STATE["last_error"]


def test_schedule_waits_for_quiet_but_not_forever(timelapse, qt_app, monkeypatch):
    timelapse.schedule("node_edit")
    timer = timelapse.STATE["timer"]
    assert timer.isActive() and timelapse.STATE["pending_label"] == "node_edit"
    started = timelapse.STATE["pending_since"]
    timelapse.schedule("parm_set")
    assert timelapse.STATE["pending_since"] == started
    assert timelapse.STATE["pending_label"] == "parm_set"
    # After MAX_GAP_S of changes the timer is not pushed back again.
    timelapse.STATE["pending_since"] = time.time() - timelapse.MAX_GAP_S - 1
    timer.start(1000)
    timelapse.schedule("connect")
    assert timer.remainingTime() < timelapse.DELAY_MS - 200
    timer.stop()


def rop(picture, frames=(1, 2, 3)):
    node = mock.MagicMock()
    parms = {
        "picture": mock.MagicMock(**{"evalAtFrame.side_effect":
                                     lambda f: picture.replace("$F", str(int(f)))}),
        "trange": mock.MagicMock(**{"eval.return_value": 1}),
        "f1": mock.MagicMock(**{"eval.return_value": frames[0]}),
        "f2": mock.MagicMock(**{"eval.return_value": frames[-1]}),
        "f3": mock.MagicMock(**{"eval.return_value": 1}),
    }
    node.parm.side_effect = parms.get
    return node


def test_a_render_is_copied_into_renders(timelapse, hou, tmp_path, monkeypatch):
    saved(hou, str(tmp_path / "proj" / "hip" / "t.hip"))
    out = tmp_path / "proj" / "render"
    out.mkdir(parents=True)
    old = out / "beauty.1.exr"
    old.write_bytes(b"old")
    os.utime(old, (0, 0))
    started = time.time()
    for frame in (2, 3):
        (out / f"beauty.{frame}.exr").write_bytes(b"new")
    hou.node.return_value = rop(str(out / "beauty.$F.exr"))
    monkeypatch.setattr(timelapse, "schedule", lambda label: None)
    timelapse.after("render", {"path": "/out/karma1"}, started)
    renders = sorted(os.listdir(tmp_path / "proj" / "timelapse" / "renders"))
    assert renders == ["0001_beauty.2.exr", "0001_beauty.3.exr"]
    assert timelapse.STATE["renders"] == 2


def test_render_progress_copies_nothing(timelapse, hou, tmp_path, monkeypatch):
    saved(hou, str(tmp_path / "t.hip"))
    monkeypatch.setattr(timelapse, "schedule", lambda label: None)
    copy = mock.MagicMock()
    monkeypatch.setattr(timelapse, "copy_render", copy)
    timelapse.after("render", {"mode": "progress", "path": "/out/r"}, time.time())
    copy.assert_not_called()


def test_configure_turns_it_off_and_names_the_folder(timelapse, hou, tmp_path):
    result = timelapse.configure(enabled=False)
    assert result["enabled"] is False and result["note"]
    saved(hou, str(tmp_path / "t.hip"))
    result = timelapse.configure(folder=str(tmp_path / "tl"))
    assert result["folder"] == str(tmp_path / "tl")
