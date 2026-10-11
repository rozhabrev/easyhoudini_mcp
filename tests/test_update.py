"""The bridge tells the agent about a new release and an old plugin copy, and
never blocks or fails for it (11.10.2026)."""
import json
import time

import pytest


@pytest.fixture
def update(tmp_path, monkeypatch):
    from bridge import update
    monkeypatch.setenv("HOUDINIMCP_HOME", str(tmp_path))
    monkeypatch.delenv("HOUDINIMCP_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(update, "__version__", "0.4.2")
    monkeypatch.setattr(update, "_state", {"latest": None, "changes": "", "told_mismatch": False})
    monkeypatch.setattr(update.os, "name", "posix")
    from bridge.onboarding import install
    monkeypatch.setattr(install, "repo_dir", lambda: None)
    return update


def _github(update, monkeypatch, tags, changelog=""):
    calls = []

    def fake(url):
        calls.append(url)
        if "api.github.com" in url:
            return json.dumps([{"name": tag} for tag in tags]).encode()
        return changelog.encode()
    monkeypatch.setattr(update, "_get", fake)
    return calls


def test_versions_compare_as_numbers(update):
    assert update.newer("0.4.10", "0.4.9")
    assert update.newer("v1.0.0", "0.9.9")
    assert not update.newer("0.4.2", "0.4.2")
    assert not update.newer("nightly", "0.4.2")
    assert not update.newer(None, "0.4.2")


def test_changes_are_the_sections_after_this_version(update):
    changelog = "# Changelog\n\n## 0.5.0 - x\nnew A\n\n## 0.4.3 - y\nfix B\n\n## 0.4.2 - z\nold C\n"
    text = update.changes_since(changelog, "0.4.2")
    assert "new A" in text and "fix B" in text and "old C" not in text


def test_offline_says_nothing_and_keeps_no_cache(update, monkeypatch):
    def offline(url):
        raise OSError("no network")
    monkeypatch.setattr(update, "_get", offline)
    update.check()
    assert update._state["latest"] is None
    assert update._read_cache() == {}
    assert update.note({}) == ""


def test_a_new_release_is_told_once_a_day(update, monkeypatch):
    calls = _github(update, monkeypatch, ["v0.4.1", "v0.5.0", "v0.4.2"], "## 0.5.0 - x\nnew A\n")
    update.check()
    first = update.note({"version": "22.0.400", "plugin": "0.4.2", "plugin_prefs": "/p/houdini22.0"})
    assert "0.5.0" in first and "new A" in first and "Do not update without a yes" in first
    assert "@v0.5.0" in first and '--prefs-dir "/p/houdini22.0" --harness none --yes' in first
    assert update.note({"plugin": "0.4.2"}) == ""

    # The next start in the same day reads the cache, not GitHub.
    update._state.update(latest=None, changes="")
    update.check()
    assert len(calls) == 2 and update._state["latest"] == "0.5.0"
    assert update.note({"plugin": "0.4.2"}) == ""

    cache = update._read_cache()
    update._write_cache({**cache, "told_at": time.time() - update.CHECK_EVERY - 1})
    assert "0.5.0" in update.note({"plugin": "0.4.2"})


def test_on_windows_the_agent_gives_the_command_to_the_user(update, monkeypatch):
    _github(update, monkeypatch, ["v0.5.0"])
    monkeypatch.setattr(update.os, "name", "nt")
    update.check()
    assert "Do not run it yourself" in update.note({"plugin": "0.4.2"})


def test_no_note_when_this_is_the_latest(update, monkeypatch):
    _github(update, monkeypatch, ["v0.4.1", "v0.4.2"])
    update.check()
    assert update.note({"plugin": "0.4.2"}) == ""


def test_an_old_plugin_copy_is_told_once(update):
    text = update.note({"version": "21.0.631"})
    assert "older than 0.4.2" in text and "--houdini-version 21.0 --harness none --yes" in text
    assert "uv tool install" not in text  # the bridge is up to date; only the plugin
    assert update.note({"version": "21.0.631"}) == ""


def test_a_newer_plugin_asks_for_a_newer_bridge(update):
    assert "@v0.5.0" in update.note({"plugin": "0.5.0"})


def test_a_clone_updates_with_git(update, monkeypatch):
    from bridge.onboarding import install
    monkeypatch.setattr(install, "repo_dir", lambda: "/src/mcp")
    command = update.install_command({"plugin_prefs": "/p"}, "0.5.0")
    assert command.startswith('git -C "/src/mcp" pull ; uv --directory "/src/mcp" run')
