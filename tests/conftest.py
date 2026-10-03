"""A stand-in `hou`, so the plugin modules import outside Houdini.

These tests cover the logic that a person cannot check by hand: when the
timelapse takes a frame, where it puts it, how a picture reaches the agent,
and that the house rules reach it once. What Houdini itself draws is checked
in a live session.
"""
import contextlib
import os
import sys
import types
from unittest import mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _fake_hou():
    hou = mock.MagicMock(name="hou")
    hou.isUIAvailable.return_value = True
    hou.hipFile.path.return_value = "/work/untitled.hip"
    hou.hipFile.isNewFile.return_value = True
    hou.text.expandString.side_effect = lambda value: value
    hou.frame.return_value = 1.0
    hou.node.return_value = None
    hou.undos.group.side_effect = lambda name: contextlib.nullcontext()
    return hou


sys.modules["hou"] = _fake_hou()


@pytest.fixture
def hou():
    """The stand-in hou, reset for each test."""
    fake = _fake_hou()
    sys.modules["hou"] = fake
    for name, module in list(sys.modules.items()):
        if name.startswith("houdinimcp") and hasattr(module, "hou"):
            module.hou = fake
    return fake


@pytest.fixture
def timelapse(hou):
    from houdinimcp.handlers import timelapse
    timelapse.STATE.update(enabled=True, folder=None, timer=None, pending_since=None,
                           pending_label="", pending_node=None, last_node=None,
                           last_shot=None, shots=0, renders=0, views=0, camera=None,
                           view_box=None, followed=None, last_error=None)
    return timelapse


@pytest.fixture(scope="session")
def qt_app():
    from PySide6.QtGui import QGuiApplication
    return QGuiApplication.instance() or QGuiApplication([])
