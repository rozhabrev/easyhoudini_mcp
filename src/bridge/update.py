"""Tell the agent when a newer release is out, and when the plugin in Houdini
is an older copy than the bridge.

The check never updates anything. It reads the release tags of the repository
at most once a day, in a thread, with a short timeout, and sends nothing but
the request itself. Offline, or when GitHub does not answer, it says nothing.
The person decides; the agent runs the install command only after a yes.

A user has two copies: the bridge, which the AI client starts, and the plugin,
which the installer copies into the Houdini prefs. One install command updates
both, and the plugin version in every answer of Houdini shows a copy that was
left behind.
"""
import json
import os
import re
import threading
import time
import urllib.request

from houdinimcp import __version__, protocol

REPOSITORY = "rozhabrev/easyhoudini_mcp"
CHECK_EVERY = 24 * 3600
TIMEOUT = 3.0
CHANGES_LIMIT = 3000

_state = {"latest": None, "changes": "", "told_mismatch": False}


def version_tuple(text: str):
    """(0, 4, 2) for "v0.4.2" or "0.4.2"; None for a tag that is not a release."""
    match = re.fullmatch(r"v?(\d+)\.(\d+)\.(\d+)", (text or "").strip())
    return tuple(int(part) for part in match.groups()) if match else None


def newer(candidate: str, current: str = None) -> bool:
    found, have = version_tuple(candidate), version_tuple(current or __version__)
    return bool(found and have and found > have)


def _cache_file() -> str:
    return os.path.join(protocol.data_dir(), "update_check.json")


def _read_cache() -> dict:
    try:
        with open(_cache_file(), encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _write_cache(cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_cache_file()), exist_ok=True)
        with open(_cache_file(), "w", encoding="utf-8") as handle:
            json.dump(cache, handle)
    except OSError:
        pass


def _get(url: str) -> bytes:
    # GitHub refuses a request without a User-Agent.
    request = urllib.request.Request(url, headers={"User-Agent": f"easyhoudini-mcp/{__version__}"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return response.read()


def latest_release() -> str:
    """The highest release tag on GitHub, for example "0.4.2"."""
    tags = json.loads(_get(f"https://api.github.com/repos/{REPOSITORY}/tags?per_page=100"))
    versions = [version_tuple(tag.get("name")) for tag in tags]
    versions = [version for version in versions if version]
    return ".".join(map(str, max(versions))) if versions else None


def changes_since(changelog: str, current: str = None) -> str:
    """The CHANGELOG sections of the releases after `current`, cut short."""
    sections = re.split(r"(?m)^(?=## )", changelog)
    picked = [section.strip() for section in sections
              if section.startswith("## ") and newer(section[3:].split()[0], current)]
    text = "\n\n".join(picked)
    return text if len(text) <= CHANGES_LIMIT else text[:CHANGES_LIMIT] + "\n..."


def check() -> None:
    """Find the latest release. Uses the cached answer for a day. Never raises."""
    if os.environ.get("HOUDINIMCP_NO_UPDATE_CHECK"):
        return
    cache = _read_cache()
    if time.time() - cache.get("checked_at", 0) < CHECK_EVERY:
        _state["latest"], _state["changes"] = cache.get("latest"), cache.get("changes", "")
        return
    try:
        latest = latest_release()
        changes = ""
        if newer(latest):
            changes = changes_since(_get(f"https://raw.githubusercontent.com/{REPOSITORY}/"
                                         f"v{latest}/CHANGELOG.md").decode("utf-8"))
    except Exception:
        return  # offline, rate limit, a changed API: try again at the next start
    _state["latest"], _state["changes"] = latest, changes
    _write_cache({**cache, "checked_at": time.time(), "latest": latest, "changes": changes})


def start() -> None:
    """Run the check in the background, so the bridge starts at once."""
    threading.Thread(target=check, name="houdinimcp-update-check", daemon=True).start()


def plugin_target(session: dict) -> str:
    """The installer arguments that put the plugin into the Houdini that answered."""
    if session.get("plugin_prefs"):
        return f'--prefs-dir "{session["plugin_prefs"]}"'
    release = ".".join((session.get("version") or "").split(".")[:2])
    return f"--houdini-version {release}" if release else ""


def install_command(session: dict, release: str = None) -> str:
    """The command that brings the plugin, and with `release` the bridge too,
    up to date. The client configs keep pointing at the same bridge command,
    so the harness step is skipped."""
    from .onboarding.install import repo_dir
    target = plugin_target(session)
    clone = repo_dir()
    installer = (f'uv --directory "{clone}" run python -m bridge.onboarding.install'
                 if clone else "houdinimcp-install")
    installer = f"{installer} {target} --harness none --yes".replace("  ", " ")
    if not release:
        return installer
    fetch = (f'git -C "{clone}" pull' if clone else
             f"uv tool install --force git+https://github.com/{REPOSITORY}@v{release}")
    return f"{fetch} ; {installer}"


def note(session: dict) -> str:
    """The note for the next tool result, or "". The new release is told at
    most once a day, an old plugin copy once for each bridge process."""
    notes = []
    latest = _state["latest"]
    cache = _read_cache() if newer(latest) else {}
    if newer(latest) and cache.get("latest") == latest and time.time() - cache.get("told_at", 0) >= CHECK_EVERY:
        _write_cache({**cache, "told_at": time.time()})
        windows = os.name == "nt"
        notes.append(
            f"A new release of this Houdini MCP is out: {latest}. This one is {__version__}. "
            f"Tell the user in their own language, with the main changes below in one or "
            f"two short lines, and ask if they want it. Do not update without a yes.\n"
            f"The update is one command; it updates the bridge and the plugin in Houdini:\n"
            f"    {install_command(session, latest)}\n"
            + ("On Windows the running bridge holds its own files, so the command fails "
               "while this AI client runs. Do not run it yourself. Give the user the "
               "command: close this AI client, paste it into PowerShell, then start Houdini "
               "and the client again.\n" if windows else
               "After a yes, run it, then tell the user to restart Houdini and this AI "
               "client.\n")
            + f"Changes: https://github.com/{REPOSITORY}/blob/main/CHANGELOG.md"
            + (f"\n\n{_state['changes']}" if _state["changes"] else ""))
    plugin = session.get("plugin")
    if session and plugin != __version__ and not _state["told_mismatch"]:
        _state["told_mismatch"] = True
        if newer(plugin):
            notes.append(
                f"The plugin in this Houdini is {plugin}, newer than this bridge "
                f"({__version__}). Tell the user, and ask to update the bridge with:\n"
                f"    {install_command(session, plugin)}")
            return "\n\n".join(notes)
        notes.append(
            f"The plugin in this Houdini is {plugin or 'older than 0.4.2'}, the bridge is "
            f"{__version__}. A plugin copy that does not match the bridge can refuse calls "
            f"or miss fixes. Tell the user, and after a yes run this command (it does not "
            f"touch the bridge, so it is safe while the client runs):\n"
            f"    {install_command(session)}\n"
            f"Then the user restarts Houdini.")
    return "\n\n".join(notes)


def report(session: dict) -> dict:
    """The versions, for session action='status'."""
    found = {"bridge": __version__, "plugin": session.get("plugin") if session else None,
             "latest_release": _state["latest"]}
    if newer(_state["latest"]):
        found["update"] = install_command(session or {}, _state["latest"])
    return found
