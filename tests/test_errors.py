"""The error log, the note on a repeated error, the hints, and the count of
changes since the last save."""
import json

import pytest


@pytest.fixture
def errors(tmp_path, monkeypatch):
    from bridge import errors
    monkeypatch.setattr(errors, "log_path", lambda: str(tmp_path / "errors.jsonl"))
    monkeypatch.setattr(errors, "_state", {"calls": 0, "seen": {}})
    return errors


def test_signature_drops_names_and_numbers(errors):
    one = errors.signature("AttributeError: 'NoneType' object has no attribute 'points'")
    two = errors.signature("AttributeError: 'NoneType' object has no attribute 'setParms'")
    assert one == two == "AttributeError: 'X' object has no attribute 'X'"


def test_the_log_keeps_the_code_and_hides_secrets(errors, tmp_path):
    errors.record("execute", "ValueError: no", mode="python",
                  code="api_key = 'abc123'\nx = 1", version="22.0.368")
    entry = json.loads((tmp_path / "errors.jsonl").read_text())
    assert entry["tool"] == "execute" and entry["houdini"] == "22.0.368"
    assert "abc123" not in entry["code"] and "x = 1" in entry["code"]


def test_the_same_error_twice_says_stop(errors):
    errors.tick()
    assert errors.record("cook", "Error: while cooking 3") == ""
    errors.tick()
    errors.tick()
    note = errors.record("cook", "Error: while cooking 7")
    assert "same error as 2 calls ago" in note


def test_summary_counts_by_signature(errors):
    for number in range(3):
        errors.record("execute", f"IndexError: list index {number} out of range")
    errors.record("cook", "Error: other")
    rows = errors.summary()
    assert rows[0]["count"] == 3 and rows[0]["tool"] == "execute"


def test_soft_errors_are_found_in_results(errors):
    result = json.dumps({"executed": False, "error": "NameError: x"})
    listed = json.dumps({"count": 2, "nodes": [{"path": "/a", "error": "ValueError: y"},
                                               {"path": "/b", "result": {}}]})
    assert errors.soft_errors(result) == ["NameError: x"]
    assert errors.soft_errors(["picture", listed]) == ["ValueError: y"]


def test_a_tool_error_is_logged_and_repeats_are_noted(errors, monkeypatch):
    from bridge import tools
    from mcp.server.mcpserver.exceptions import ToolError

    def failing(mode: str = "x"):
        raise ValueError("Unknown mode 'errors'.")

    guarded = tools._guarded(failing, "node_inspect")
    monkeypatch.setitem(tools.RULES, "sent", True)
    with pytest.raises(ToolError):
        guarded(mode="errors")
    with pytest.raises(ToolError, match="same error"):
        guarded(mode="errors")
    assert errors.summary()[0]["count"] == 2


def test_unsaved_changes_are_counted(monkeypatch):
    from bridge import tools
    monkeypatch.setitem(tools._unsaved_calls, "count", 0)
    notes = [tools._unsaved("parm_set", {}) for _ in range(tools.SAVE_EVERY)]
    assert not any(notes[:-1]) and "not been saved for 10" in notes[-1]
    assert tools._unsaved("node_inspect", {}) == ""
    tools._unsaved("scene_file", {"mode": "save"})
    assert tools._unsaved_calls["count"] == 0


def test_hint_names_the_missing_node_and_its_neighbours(hou):
    from houdinimcp import hints
    hints.hou = hou
    nodes = {"/obj": object(), "/obj/geo1": object()}

    class Child:
        def __init__(self, name):
            self._name = name

        def name(self):
            return self._name

    parent = type("P", (), {"children": lambda self: [Child("geo1"), Child("ai01_box")]})()
    hou.node.side_effect = lambda path: parent if path == "/obj" else nodes.get(path)
    text = hints.hint("AttributeError: 'NoneType' object has no attribute 'points'",
                      "g = hou.node('/obj/ai01_bxo').geometry()\nprint(g.points())")
    assert "/obj has no node 'ai01_bxo'" in text and "ai01_box" in text
    with pytest.raises(ValueError, match="ai01_box"):
        hints.need("/obj/ai01_bxo")


def test_hint_for_a_wrong_api_guess():
    from houdinimcp import hints
    assert "stage" in hints.hint("AttributeError: 'LopNode' object has no attribute 'geometry'")
    assert "inputLabels" in hints.hint("AttributeError: 'SopNode' object has no attribute "
                                       "'inputLabel'")


def test_unknown_mode_names_the_closest():
    from houdinimcp.tools import unknown_mode
    assert "Did you mean 'parms'" in str(unknown_mode("parm", ("info", "parms")))
