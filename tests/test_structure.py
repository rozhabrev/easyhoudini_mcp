"""The bridge warns when the agent repeats a box or a subnet (11.10.2026)."""
import json


def test_only_calls_that_make_a_box_or_a_subnet_are_checked():
    from bridge import structure
    assert structure.makes_structure("node_edit", {"node_type": "subnet"})
    assert structure.makes_structure("node_edit", {"items": [{"node_type": "box"}, {"node_type": "subnet"}]})
    assert not structure.makes_structure("node_edit", {"node_type": "box"})
    assert structure.makes_structure("execute", {"source": "b = n.createNetworkBox()"})
    assert not structure.makes_structure("execute", {"source": "print(1)"})
    assert not structure.makes_structure("parm_set", {"path": "/obj/a"})


def test_a_repeated_box_comes_back_as_a_note(monkeypatch):
    from bridge import structure
    report = [{"network": "/obj/wheel", "nodes": 9, "repeated_boxes": ["01 controls"],
               "empty_boxes": ["01 CONTROLS"]}]
    monkeypatch.setattr(structure, "call_json",
                        lambda *a, **k: json.dumps({"stdout": json.dumps(report)}))
    text = structure.note("execute", {"source": "net.createNetworkBox()"})
    assert "/obj/wheel" in text and "repeated boxes: 01 controls" in text
    assert "empty boxes" not in text  # a box made in this call may be filled by the next


def test_a_clean_scene_gives_no_note(monkeypatch):
    from bridge import structure
    monkeypatch.setattr(structure, "call_json", lambda *a, **k: json.dumps({"stdout": "[]"}))
    assert structure.note("node_edit", {"node_type": "subnet"}) == ""


def test_the_save_reports_empty_boxes_and_subnets(monkeypatch):
    from bridge import structure
    from bridge.tools import scene_file
    report = [{"network": "/obj/geo1", "nodes": 5, "empty_boxes": ["02 CUBE"], "empty_subnets": ["ai_cube1"]}]
    seen = {}

    def fake(name, params, timeout=None):
        if name == "execute":
            seen["layout"] = params["source"].startswith("LAYOUT = True")
            return json.dumps({"stdout": json.dumps(report)})
        return json.dumps({"saved": True})
    monkeypatch.setattr(structure, "call_json", fake)
    monkeypatch.setattr(scene_file, "call_json", fake)
    out = json.loads(scene_file.tool(mode="save", path="/x.hip"))
    assert out["layout_check"] == report and seen["layout"]
    assert "Fix every entry now" in out["layout_check_todo"]


def test_the_core_says_read_the_network_and_reuse_it():
    from bridge import cli
    assert "Before the first change of each request, read the network" in cli.RULES
    assert "never one per operation" in cli.RULES
    assert "look for a box with" in cli.RULES
    assert "copied to points, never one node for each part" in cli.RULES
