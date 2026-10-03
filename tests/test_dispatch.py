import sys
import types

import pytest


def tool(monkeypatch, name, run, mutates):
    from houdinimcp import tools
    module = types.ModuleType(f"houdinimcp.tools.{name}")
    module.run = run
    module.MUTATES = mutates
    monkeypatch.setitem(sys.modules, module.__name__, module)
    monkeypatch.setattr(tools, "MODULES", tools.MODULES + [name])
    return tools


@pytest.fixture
def seen(timelapse, monkeypatch):
    calls = []
    monkeypatch.setattr(timelapse, "after",
                        lambda command, params, started, result=None, mark=None: calls.append((command, params)))
    return calls


def test_a_mutating_call_tells_the_timelapse(monkeypatch, seen):
    tools = tool(monkeypatch, "fake_edit", lambda **p: {"ok": 1}, True)
    assert tools.dispatch("fake_edit", {"mode": "create"}) == {"ok": 1}
    assert seen == [("fake_edit", {"mode": "create"})]


def test_a_read_does_not(monkeypatch, seen):
    tools = tool(monkeypatch, "fake_read", lambda **p: 1, False)
    tools.dispatch("fake_read", {})
    assert seen == []


def test_a_failed_call_does_not(monkeypatch, seen):
    def broken(**params):
        raise ValueError("no")
    tools = tool(monkeypatch, "fake_broken", broken, True)
    with pytest.raises(ValueError):
        tools.dispatch("fake_broken", {})
    assert seen == []


def test_a_waiting_call_tells_it_when_it_ends(monkeypatch, seen):
    def waits(**params):
        yield 1, None
        return {"done": True}
    tools = tool(monkeypatch, "fake_wait", waits, True)
    generator = tools.dispatch("fake_wait", {})
    next(generator)
    assert seen == []
    with pytest.raises(StopIteration) as end:
        next(generator)
    assert end.value.value == {"done": True}
    assert seen == [("fake_wait", {})]
