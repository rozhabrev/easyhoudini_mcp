"""The timelapse moves the display flag only inside the work of the agent,
and select shows the node that it names."""
from unittest import mock

import pytest


class Sop:
    def __init__(self, session_id, parent=None, inputs=()):
        self.id, self._parent, self._inputs = session_id, parent, inputs
        self.flag = False

    def sessionId(self):
        return self.id

    def parent(self):
        return self._parent

    def outputs(self):
        return ()

    def isDisplayFlagSet(self):
        return self.flag

    def inputAncestors(self):
        return self._inputs

    def setDisplayFlag(self, on):
        self.flag = on

    def type(self):
        return mock.Mock(**{"name.return_value": "subnet"})


@pytest.fixture
def follow(hou, monkeypatch):
    from houdinimcp.handlers import follow
    hou.SopNode, hou.LopNode = Sop, type("Lop", (), {})
    hou.Error = Exception
    follow.hou = hou
    monkeypatch.setattr(follow, "MADE", set())
    return follow


def _chain(display_id):
    network = mock.Mock()
    shown = Sop(display_id)
    network.displayNode.return_value = shown
    return network, shown


def test_the_flag_stays_on_a_node_of_the_user(follow):
    network, shown = _chain(1)
    work = Sop(2, network, inputs=(shown,))
    follow.MADE.add(2)
    assert follow.advance_display(work) is None
    assert not work.flag


def test_the_flag_moves_along_the_chain_of_the_agent(follow):
    network, shown = _chain(1)
    work = Sop(2, network, inputs=(shown,))
    follow.MADE.update({1, 2})
    assert follow.advance_display(work) is work


def test_select_follows_the_node_it_shows(follow, hou):
    node = Sop(5)
    hou.node.side_effect = lambda path: node if path == "/stage/a/sub/x" else None
    result = {"network": "/stage/a/sub", "viewer": "/stage/a"}
    assert follow.touched("select", {"paths": ["/stage/a/sub/x"], "show": True},
                          result) is node
