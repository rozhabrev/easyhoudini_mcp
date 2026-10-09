"""The bridge side of the socket, and the headless Houdini it can start.

The MCP tools call `call()`. Nothing else in the bridge touches the socket.
"""
import json
import logging
import os
import shutil
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from mcp.server.mcpserver.exceptions import ToolError

from houdinimcp import protocol

logger = logging.getLogger("HoudiniMCP.bridge")

HEADLESS_DISABLED = os.getenv("HOUDINIMCP_NO_HEADLESS", "").strip() in ("1", "true", "yes")
# hython runs this file by path, because it cannot import from the bridge venv.
HEADLESS_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(protocol.__file__)),
                               "headless.py")

_connection = None
_hython = None
# The port the caller chose with session action='attach'. Without one the bridge
# picks, and it refuses to pick when the choice is not obvious.
_attached_port = None
_last_session = None


class HoudiniError(ToolError):
    """Houdini could not be reached, or it refused the command.

    The message says what to do next. Show it to the user as it is.
    It is a ToolError because the MCP SDK hides the text of any other exception
    and sends only "Error executing tool <name>".
    """


@dataclass
class Connection:
    host: str
    port: int
    sock: socket.socket = None
    connected_since: float = None
    last_command_at: float = None
    command_count: int = 0
    # The plugin answers one call at a time, and the MCP client can send the
    # next call while the last one still runs in Houdini.
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    running: dict = None

    def connect(self) -> bool:
        if self.sock is not None:
            return True
        if not self.port:
            return False
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=10)
            self.connected_since = time.monotonic()
            logger.info(f"Connected to Houdini at {self.host}:{self.port}")
            return True
        except OSError as error:
            logger.info(f"No Houdini on {self.host}:{self.port}: {error}")
            self.sock = None
            self.connected_since = None
            return False

    def disconnect(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError as error:
                logger.error(f"Error closing the socket: {error}")
        self.sock = None
        self.connected_since = None

    def status(self) -> dict:
        return {
            "connected": self.sock is not None,
            "host": self.host,
            "port": self.port,
            "connected_since": self.connected_since,
            "last_command_at": self.last_command_at,
            "command_count": self.command_count,
        }

    def send(self, command: dict, timeout: float, label: str = None) -> dict:
        """Send one command and wait for its answer.

        A call that arrives while another one runs is refused at once, with what
        runs and for how long: Houdini cannot answer it before the first ends,
        and a caller that waits in silence retries and starts the work twice.
        """
        if not self.lock.acquire(blocking=False):
            raise HoudiniError(self.busy_message())
        try:
            self.running = {"command": command["type"], "label": label,
                            "since": time.monotonic()}
            return self._send(command, timeout)
        finally:
            self.running = None
            self.lock.release()

    def busy_message(self) -> str:
        running = self.running or {}
        seconds = time.monotonic() - running.get("since", time.monotonic())
        what = running.get("label") or f"'{running.get('command', 'a call')}'"
        return (f"Houdini on port {self.port} still runs {what}, sent {seconds:.0f} seconds "
                f"ago, and it answers one call at a time. The work goes on. Wait and call "
                f"again, read a background job with execute mode='job', or stop the work "
                f"with session action='interrupt'.")

    def _send(self, command: dict, timeout: float) -> dict:
        """A plugin restart kills the socket but not this object, so a lost
        connection is opened again once. The plugin that went away never read
        the command, so the second try cannot repeat work."""
        for attempt in (1, 2):
            if not self.connect():
                raise HoudiniError(start_hint(self.port))
            try:
                self.sock.settimeout(timeout)
                self.sock.sendall(protocol.encode(command))
                self.last_command_at = time.monotonic()
                self.command_count += 1
                return protocol.receive(self.sock)
            except socket.timeout:
                self.disconnect()
                raise HoudiniError(
                    f"Houdini on port {self.port} did not answer '{command['type']}' in "
                    f"{timeout:.0f} seconds. The work goes on: a timeout stops the wait, "
                    f"not the work. Call session with action='interrupt' to stop it, or "
                    f"wait and call session with action='status'. Do not start a second "
                    f"Houdini, and do not send the call again: it would run twice."
                )
            except OSError as error:
                self.disconnect()
                if attempt == 1:
                    logger.info(f"Connection lost ({error}); connecting again.")
                    continue
                raise HoudiniError(
                    f"The connection to Houdini failed on '{command['type']}': {error}. "
                    f"{start_hint(self.port)}"
                )


def start_hint(port: int = None) -> str:
    """What the user must do to get a Houdini that answers.

    A Houdini that runs but does not accept is busy, not absent: a cook or a
    render holds the main thread, and the plugin cannot accept until it ends.
    To start a second Houdini then is the worst answer, so never say it.
    `port` is the session the caller wants; only that one is named then.
    """
    busy = [entry for entry in live_sessions(probe=False)
            if process_is_alive(entry.get("pid")) and port in (None, entry["port"])]
    if port and busy:
        return (f"{describe(busy[0])} runs and does not accept a call, so it is busy: a "
                f"cook, a simulation, a render or a script holds it. Wait and call again, "
                f"or stop the work with session action='interrupt'. Do not start another "
                f"Houdini.")
    if port and protocol.sessions():
        return (f"The Houdini on port {port} stopped. Call session with action='list' to "
                f"see the sessions that are there, then action='attach' with the port you "
                f"want.")
    if busy:
        names = ", ".join(f"pid {entry.get('pid')} on port {entry['port']}"
                          f"{' (GUI)' if entry.get('ui') else ''}" for entry in busy)
        return (f"Houdini runs ({names}) and does not answer, so it is busy: a cook, a "
                f"simulation or a render holds it. Wait and call again. Do not start "
                f"another Houdini: a second one takes work and memory from this one.")
    if HEADLESS_DISABLED:
        return ("No Houdini listens for the bridge, and HOUDINIMCP_NO_HEADLESS stops the "
                "bridge from starting one. Start Houdini, or unset that variable.")
    if not find_hython():
        return ("No Houdini listens for the bridge, and no hython was found to start one. "
                "Start Houdini, or set HFS to a Houdini install.")
    return ("No Houdini listens for the bridge. Start Houdini, or call session with "
            "action='start' to run a headless one.")


def process_is_alive(pid) -> bool:
    """True when a process with this id runs. Used only to tell 'busy' from
    'gone', so a reused process id costs nothing."""
    if not pid:
        return False
    if os.name == "nt":
        import ctypes
        # SYNCHRONIZE alone: enough to open a live process, and it never asks
        # for rights that a normal user does not have.
        handle = ctypes.windll.kernel32.OpenProcess(0x00100000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, ValueError):
        return False


def live_sessions(probe: bool = True) -> list:
    """Every Houdini that announced itself, with the ones that answer marked.

    A Houdini that was killed leaves its file behind, so the port is the truth.
    `probe=False` skips the probe, for a message that must not wait.
    """
    found = []
    for entry in protocol.sessions():
        entry = dict(entry)
        if probe:
            # The socket this bridge already holds is proof, and costs no probe.
            live = _connection is not None and _connection.sock is not None \
                and _connection.port == entry["port"]
            entry["answers"] = live or port_is_listening(entry["port"])
        entry["running"] = process_is_alive(entry.get("pid"))
        if not entry["running"] and not entry.get("answers"):
            # A Houdini that was killed cannot take its own file away. Nobody
            # else will, so the list would grow with dead sessions for ever.
            protocol.withdraw(entry["port"])
            continue
        found.append(entry)
    return found


def describe(entry: dict) -> str:
    """One session as a short line a caller can choose from."""
    return (f"port {entry['port']}: Houdini {entry.get('version', '?')} "
            f"{'with a window' if entry.get('ui') else 'headless'}, "
            f"pid {entry.get('pid')}, file {entry.get('hip') or 'none'}"
            f"{'' if entry.get('answers', True) else ', busy'}")


def choose_session(entries: list) -> Optional[dict]:
    """The one session to talk to, from every Houdini that runs. None when no
    Houdini runs at all.

    The graphical session is where the user works, so it wins over any headless
    one. When it is busy, the answer is to wait for it, never to talk to a
    headless session instead: that session holds another scene, and often
    another Houdini version. Several graphical sessions, or several headless
    ones and no window, is a real choice, and only the caller can make it.
    """
    if not entries:
        return None
    with_ui = [entry for entry in entries if entry.get("ui")]
    pool = with_ui or entries
    if len(pool) == 1:
        if pool[0].get("answers"):
            return pool[0]
        raise HoudiniError(
            f"{describe(pool[0])} runs and does not answer, so it is busy: a cook, a "
            f"simulation or a render holds it. Wait, then call again. The bridge does not "
            f"send your command to another session, because that one holds another scene. "
            f"To work in another session on purpose, call session with action='attach' "
            f"and its port.")
    raise HoudiniError(
        f"{len(pool)} Houdini sessions run, and the bridge must not guess which one "
        f"holds your work. {'; '.join(describe(entry) for entry in entries)}. Call "
        f"session with action='attach' and the port you want.")


def installs() -> list:
    """Every hython on this machine, newest first, as {"version", "hython"}."""
    from .onboarding.houdini import find_installs
    name = "hython.exe" if os.name == "nt" else "hython"
    found = []
    for install in find_installs():
        if install.executable:
            hython = os.path.join(os.path.dirname(install.executable), name)
            if os.path.isfile(hython):
                found.append({"version": install.version, "hython": hython})
    return found


def find_hython(version: str = None) -> Optional[str]:
    """The hython to start: of `version` ("21.0" or "21.0.829") when given.

    Without a version it is the version of the Houdini window that runs: a test
    in another release reads other preferences and other packages, and its
    answer does not hold for the session of the user. Then $HFS, hython on the
    PATH, and the newest install.
    """
    found = installs()
    if version:
        match = next((entry["hython"] for entry in found if entry["version"] == version
                      or entry["version"].startswith(version + ".")), None)
        if not match:
            raise HoudiniError(f"Houdini {version} is not installed. Installed: "
                               f"{', '.join(entry['version'] for entry in found) or 'none'}.")
        return match
    window = next((entry.get("version") for entry in protocol.sessions()
                   if entry.get("ui") and process_is_alive(entry.get("pid"))), None)
    if window:
        match = next((entry["hython"] for entry in found if entry["version"] == window), None)
        if match:
            return match
    hfs = os.environ.get("HFS")
    if hfs:
        for name in ("hython", "hython.exe"):
            candidate = os.path.join(hfs, "bin", name)
            if os.path.isfile(candidate):
                return candidate
    return shutil.which("hython") or (found[0]["hython"] if found else None)


def port_is_listening(port: int, host: str = "localhost") -> bool:
    """True when a plugin accepts a connection on this port."""
    if not port:
        return False
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def houdini_env() -> dict:
    """The environment of a Houdini that the bridge starts.

    On Windows it names the prefs directory of a Houdini started from the Start
    menu. Without that, a bridge started from a shell that sets HOME (Git Bash
    does) gives Houdini $HOME/houdiniX.Y: other prefs, no plugin, and a stray
    directory. Houdini puts the release in place of __HVER__.
    """
    from .onboarding.houdini import prefs_dir_for
    environment = os.environ.copy()
    if os.name == "nt" and not environment.get("HOUDINI_USER_PREF_DIR"):
        environment["HOUDINI_USER_PREF_DIR"] = prefs_dir_for("__HVER__")
    return environment


def _wait_for_new_session(process: subprocess.Popen, known: set, wait_seconds: float):
    """Wait for a session that was not there before, and attach to it.

    A new Houdini must not take the place of one that already runs, so the wait
    looks for a port that is new, not for any port.
    """
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read().decode(errors="replace")[-800:] if process.stdout else ""
            raise HoudiniError(f"Houdini stopped before it could listen:\n{output}")
        for entry in protocol.sessions():
            if entry["port"] not in known and port_is_listening(entry["port"]):
                attach(entry["port"])
                return entry
        time.sleep(0.5)
    return None


def start_headless(version: str = None, wait_seconds: float = 90.0) -> str:
    """Start a headless Houdini and wait for it to listen.

    A Houdini that already runs is left alone: this adds a session, it does not
    replace one. The bridge then talks to the new one. See find_hython for the
    version it starts.
    """
    global _hython
    hython = find_hython(version)
    if not hython:
        raise HoudiniError("No hython was found. Set HFS to a Houdini install, or start "
                           "Houdini yourself.")
    known = {entry["port"] for entry in protocol.sessions()}
    _hython = subprocess.Popen([hython, HEADLESS_SCRIPT], env=houdini_env(),
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        started = _wait_for_new_session(_hython, known, wait_seconds)
    except HoudiniError:
        _hython = None
        raise
    if started:
        return (f"A headless Houdini {started.get('version', '')} is ready on port "
                f"{started['port']}, and this bridge now talks to it.")
    stop_headless()
    raise HoudiniError(f"hython did not listen within {wait_seconds:.0f} seconds. "
                       f"Houdini may want a license. Start Houdini yourself and try again.")


def start_gui(hip: str = None, version: str = None, wait_seconds: float = 240.0) -> str:
    """Start Houdini with its window, apart from the bridge, and wait for the
    plugin to listen. The bridge does not stop it. hip is a file to open."""
    hython = find_hython(version)
    houdini = hython and os.path.join(os.path.dirname(hython),
                                      "houdini.exe" if os.name == "nt" else "houdini")
    if not houdini or not os.path.isfile(houdini):
        raise HoudiniError("No Houdini was found. Set HFS to a Houdini install, or start "
                           "Houdini yourself.")
    if hip and not os.path.isfile(hip):
        raise HoudiniError(f"There is no file at {hip}.")
    detach = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
              if os.name == "nt" else {"start_new_session": True})
    known = {entry["port"] for entry in protocol.sessions()}
    # The first start with a new preferences directory opens the usage
    # statistics question and the Start Here window, both over the viewport.
    # This is a Houdini that the bridge starts, so the choice is the caller's,
    # not a change to what the user set.
    environment = {**houdini_env(), "HOUDINI_NO_START_PAGE_SPLASH": "1"}
    process = subprocess.Popen([houdini] + ([hip] if hip else []), env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, **detach)
    started = _wait_for_new_session(process, known, wait_seconds)
    if started:
        return (f"Houdini {started.get('version', '')} is ready on port {started['port']}, "
                f"and this bridge now talks to it.")
    raise HoudiniError(f"Houdini started, but it did not listen within "
                       f"{wait_seconds:.0f} seconds. It may still load, or want a license, "
                       f"or the plugin is not installed: run houdinimcp-install. Look at the "
                       f"window, then call session with action='status'.")


def stop_headless() -> str:
    """Stop the headless Houdini that this bridge started."""
    global _hython
    if not _hython or _hython.poll() is not None:
        _hython = None
        return "This bridge does not run a headless Houdini."
    _hython.terminate()
    try:
        _hython.wait(timeout=5)
    except subprocess.TimeoutExpired:
        _hython.kill()
        _hython.wait()
    _hython = None
    return "The headless Houdini stopped."


def headless_is_ours() -> bool:
    return _hython is not None and _hython.poll() is None


def attach(port: int) -> dict:
    """Send every command from now on to the Houdini on this port."""
    global _attached_port
    if _connection is not None and _connection.running and _connection.port != port:
        raise HoudiniError(_connection.busy_message())
    if not port_is_listening(port):
        raise HoudiniError(f"No Houdini answers on port {port}. Call session with "
                           f"action='list' to see the sessions that do.")
    if _connection is not None and _connection.port != port:
        _connection.disconnect()
        _connection.port = port
    _attached_port = port
    return {"attached_port": port}


def connection(auto_start: bool = True) -> Connection:
    """The connection to the chosen Houdini. Starts a headless one if none listens."""
    global _connection
    if _connection is None:
        _connection = Connection(host="localhost", port=None)
    if _connection.sock is not None:
        return _connection

    if _attached_port:
        # A caller that chose a session must never be moved to another one in
        # silence: a command that lands in the wrong Houdini reads as a scene
        # that lost its work.
        if port_is_listening(_attached_port):
            _connection.port = _attached_port
            return _connection
        entry = next((entry for entry in protocol.sessions()
                      if entry["port"] == _attached_port), None)
        if entry and process_is_alive(entry.get("pid")):
            raise HoudiniError(
                f"The Houdini this session is attached to ({describe(entry)}) runs and "
                f"does not answer, so it is busy. Wait, then call again. The bridge does "
                f"not send your command to another session.")
        raise HoudiniError(
            f"The Houdini on port {_attached_port}, which this session is attached to, "
            f"stopped. Call session with action='list' to see the sessions that are "
            f"there, then action='attach' with the port you want, or action='detach' "
            f"to let the bridge choose.")

    chosen = choose_session(live_sessions())
    if chosen is None and auto_start and not HEADLESS_DISABLED:
        start_headless()  # attaches to the session it started
        return _connection
    _connection.port = chosen["port"] if chosen else None
    return _connection


def interrupt(port: int = None) -> str:
    """Ask the plugin on a port to stop the call that runs there now.

    The request goes over a new connection: a thread of the plugin reads it
    while the call holds the main thread of Houdini, so it reaches a Houdini
    on another machine through the same tunnel as the calls. A plugin older
    than that thread does not answer it; then the bridge writes the
    interrupt file that the watchdog of the plugin looks for, which works
    only when the plugin runs on this machine.
    """
    port = port or (_connection.port if _connection else None) or _attached_port
    if not port:
        raise HoudiniError("No Houdini is attached. Call session with action='list' and "
                           "give the port.")
    answer = _ask_to_stop(port)
    if answer is None:
        if not any(entry["port"] == port for entry in protocol.sessions()):
            raise HoudiniError(f"The Houdini on port {port} did not take the stop, and "
                               f"no Houdini on this machine announced that port. Call "
                               f"session with action='list' and give the port.")
        os.makedirs(os.path.dirname(protocol.interrupt_file(port)), exist_ok=True)
        with open(protocol.interrupt_file(port), "w"):
            pass
    elif answer.get("status") == "error":
        raise HoudiniError(f"Houdini on port {port} refused the stop: "
                           f"{answer.get('message')}")
    elif not (answer.get("result") or {}).get("stopping"):
        return f"Houdini on port {port} runs no call now: there is nothing to stop."
    # Give the call time to stop, so the report says whether Houdini is back.
    deadline = time.monotonic() + 6.0
    while time.monotonic() < deadline:
        ours = _connection is not None and _connection.port == port
        if ours and _connection.running:
            pass
        elif (ours and _connection.sock is not None) or port_is_listening(port):
            return f"The call on port {port} stopped, and Houdini answers again."
        time.sleep(0.2)
    return (f"Asked the call on port {port} to stop, and Houdini does not answer yet. One "
            f"long call into Houdini, such as one cook, ends before the stop can act; a "
            f"script that catches BaseException in a loop never lets it act. Wait and call "
            f"session action='status'.")


def _ask_to_stop(port: int, host: str = "localhost", wait: float = 5.0):
    """Send "interrupt" on a connection of its own. The answer, or None when
    the plugin does not answer it (an older plugin, or no plugin)."""
    try:
        with socket.create_connection((host, port), timeout=wait) as sock:
            sock.settimeout(wait)
            sock.sendall(protocol.encode({"type": "interrupt", "params": {}}))
            return protocol.receive(sock)
    except (OSError, ValueError):
        return None


def detach() -> dict:
    """Let the bridge choose the session again."""
    global _attached_port
    if _connection is not None and _connection.running:
        raise HoudiniError(_connection.busy_message())
    _attached_port = None
    if _connection is not None:
        _connection.disconnect()
    return {"attached_port": None}


def status() -> dict:
    """What the bridge knows about Houdini, without starting anything.

    It never raises: this is the report a caller reads to repair the state that
    makes every other tool refuse.
    """
    report = {}
    try:
        live = connection(auto_start=False)
        report.update(live.status())
        # A live socket is proof enough, and costs no probe.
        report["port_is_listening"] = live.sock is not None or port_is_listening(live.port)
    except HoudiniError as error:
        report.update({"connected": False, "port_is_listening": False,
                       "problem": str(error)})
    report["headless_started_by_bridge"] = headless_is_ours()
    report["attached_port"] = _attached_port
    report["sessions"] = live_sessions()
    try:
        report["hython"] = find_hython()
    except HoudiniError as error:
        report["hython"] = str(error)
    return report


def call(command: str, params: Dict[str, Any] = None, timeout: float = 60.0,
         label: str = None) -> Any:
    """Run one command in Houdini and return its result.

    Raises HoudiniError with the next action in the message. Every tool uses
    this, so no tool has to know about the socket.
    """
    global _last_session
    started = time.monotonic()
    response = connection().send({"type": command, "params": params or {}}, timeout, label)
    _last_session = {**response.get("session", {}), "seconds": round(time.monotonic() - started, 3)}
    if response.get("status") == "error":
        raise HoudiniError(f"Houdini refused '{command}' ({session_line()}): "
                           f"{response.get('message', 'no message')}")
    return response.get("result", {})


def session_line() -> str:
    """One line that names the Houdini which answered last.

    A result that does not say which session made it is the most costly failure
    of this bridge: the caller reads the empty scene of a stray session as a
    scene that lost its nodes.
    """
    if not _last_session:
        return "no Houdini has answered yet"
    return (f"Houdini {_last_session.get('version', '?')} "
            f"{'with a window' if _last_session.get('ui') else 'headless'}, "
            f"pid {_last_session.get('pid')}, port {_last_session.get('port')}, "
            f"file {_last_session.get('hip') or 'none'}")


def call_json(command: str, params: Dict[str, Any] = None, timeout: float = 60.0,
              label: str = None) -> str:
    """`call`, as the JSON text that an MCP tool returns, with the session that
    answered and the time it took."""
    result = call(command, params, timeout, label)
    if isinstance(result, dict):
        result = {**result, "_session": session_line(), "_seconds": _last_session["seconds"]}
    else:
        result = {"result": result, "_session": session_line(),
                  "_seconds": _last_session["seconds"]}
    return json.dumps(result, indent=2, default=str)


def shutdown():
    """Close the socket and stop a headless Houdini that this bridge started."""
    global _connection
    if _connection is not None:
        _connection.disconnect()
        _connection = None
    stop_headless()


def last_version() -> str:
    """The Houdini build that answered last, for example "21.0.829".

    The documentation must match the session the caller works in, and asking
    Houdini for its version on every documentation read would need Houdini for
    a read that does not otherwise touch it.
    """
    if _last_session:
        return _last_session.get("version")
    for session in protocol.sessions():
        if session.get("version"):
            return session["version"]
    return None
