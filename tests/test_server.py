"""The plugin answers an interrupt while the main thread holds a call."""
import os
import socket
import time

import pytest

from houdinimcp import protocol


@pytest.fixture
def server(hou, tmp_path, monkeypatch):
    monkeypatch.setattr(protocol, "SESSIONS_DIR", str(tmp_path))
    hou.isUIAvailable.return_value = False
    from houdinimcp import server as module, watchdog
    monkeypatch.setattr(module, "hou", hou)
    monkeypatch.setattr(module.watchdog, "start", lambda: None)
    monkeypatch.setattr(module, "identity", lambda: {"pid": 1})
    plugin = module.HoudiniMCPServer(port=0)
    plugin.start()
    yield plugin
    plugin.stop()
    watchdog._current = None


def _call(port, message):
    with socket.create_connection(("localhost", port), timeout=5) as sock:
        sock.settimeout(5)
        sock.sendall(protocol.encode(message))
        return protocol.receive(sock)


def test_interrupt_is_answered_without_the_main_thread(server, monkeypatch):
    from houdinimcp import watchdog
    # A call holds the main thread: nothing runs _process_server here.
    monkeypatch.setattr(watchdog, "_current", {"command": "execute"})
    answer = _call(server.port, {"type": "interrupt", "params": {}})
    assert answer["result"]["stopping"] == "execute"
    assert os.path.exists(protocol.interrupt_file(server.port))


def test_the_bridge_stops_a_call_through_the_socket(server, monkeypatch):
    from bridge import connection
    from houdinimcp import watchdog
    monkeypatch.setattr(watchdog, "_current", None)
    assert "nothing to stop" in connection.interrupt(server.port)


def test_other_calls_wait_for_the_main_thread(server, monkeypatch):
    from houdinimcp import server as module
    monkeypatch.setattr(module, "dispatch", lambda name, params: {"ran": name})
    with socket.create_connection(("localhost", server.port), timeout=5) as sock:
        sock.settimeout(5)
        sock.sendall(protocol.encode({"type": "playbar", "params": {}}))
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and not any(server.clients.values()):
            time.sleep(0.02)
        server._process_server()
        assert protocol.receive(sock)["result"] == {"ran": "playbar"}
