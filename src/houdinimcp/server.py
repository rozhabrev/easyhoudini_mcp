"""Houdini-side TCP server that receives JSON commands from the MCP bridge."""
import inspect
import os
import select
import socket
import threading
import time
import traceback

import hou

from . import hints, protocol, watchdog
from .tools import dispatch

EXTENSION_NAME = "Houdini MCP"
EXTENSION_VERSION = (0, 3)
EXTENSION_DESCRIPTION = "Connect Houdini to Claude via MCP"

WAITING = object()   # a call that waits for the event loop; see _step


def identity() -> dict:
    """Which Houdini this is. Every answer carries it, so a caller can never
    work in a session that it did not mean to reach."""
    return {
        "pid": os.getpid(),
        "version": hou.applicationVersionString(),
        "product": hou.applicationName(),
        "ui": hou.isUIAvailable(),
        "hip": hou.hipFile.path(),
    }


LOG_BYTES = 2 * 1024 * 1024


def log_path() -> str:
    return os.path.join(protocol.data_dir(), "plugin_errors.log")


def log_error(name):
    """Write the traceback of the exception being handled to the log file of
    the plugin, never to the console of Houdini."""
    path = log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > LOG_BYTES:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {name}\n"
                         f"{traceback.format_exc()}")
    except OSError:
        pass


def identity_quiet() -> dict:
    """identity() from a thread that is not the main one: hou can be busy
    there, so only what needs no call into Houdini."""
    return {"pid": os.getpid()}


class HoudiniMCPServer:
    """The socket of the plugin.

    One thread reads: it accepts the clients and takes the frames off their
    sockets. The main thread of Houdini runs the calls, one after the other.
    The reader answers one message itself, at once: "interrupt". A call that
    holds the main thread holds the event loop too, so an interrupt that
    waited for the main thread would wait for the very call it must stop. The
    bridge used to ask with a file on its own disk, and a bridge on another
    machine (through a tunnel) could not stop anything (09.10.2026).
    """

    def __init__(self, host='localhost', port=None):
        self.host = host
        # 0 tells the operating system to pick a free port. See protocol.PORT_FILE.
        self.port = port if port is not None else (protocol.FORCED_PORT or 0)
        self.running = False
        self.socket = None
        # Every client with the commands it sent that have not run yet.
        # Several clients can hold a socket: a bridge, and a script that the
        # agent runs for a long job. Their calls run one after the other.
        self.clients = {}
        self._buffers = {}    # the bytes of each client that do not make a frame yet
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()   # one frame at a time on the wire
        self._wake = threading.Event()
        self._reader = None
        self.busy = False
        self.waiting = None   # the call that waits for the event loop
        # One object, so removeEventLoopCallback finds the callback it added.
        self._poll = self._process_server

    def start(self):
        """Listen on the port, and start the reader thread. In a GUI the
        Houdini event loop drives the calls.

        In hython there is no event loop, so the caller runs serve_forever.
        """
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            # Windows shares a bound port unless the first owner refuses it.
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.socket.bind((self.host, self.port))
        except OSError as error:
            self.socket.close()
            self.socket = None
            raise OSError(
                f"HoudiniMCP cannot listen on {self.host}:{self.port}: {error}. "
                f"Another process holds the port, or Windows reserved it (WinError "
                f"10013: see `netsh interface ipv4 show excludedportrange protocol=tcp`). "
                f"Unset HOUDINIMCP_PORT to let the operating system pick a free port."
            ) from error
        self.socket.listen(8)
        self.port = self.socket.getsockname()[1]
        protocol.announce(self.port, identity())
        watchdog.start()
        self.socket.setblocking(False)
        self.running = True
        self._reader = threading.Thread(target=self._read_loop, name="houdinimcp-reader",
                                        daemon=True)
        self._reader.start()
        if hou.isUIAvailable():
            hou.ui.addEventLoopCallback(self._poll)
        print(f"HoudiniMCP server started on {self.host}:{self.port}")

    def serve_forever(self):
        """Run the calls from this thread. For hython, which has no event loop."""
        while self.running:
            self._wake.wait(0.5)
            self._wake.clear()
            try:
                self._process_server()
            except Exception:
                # The loop must outlive one bad call. A plugin that stops here
                # reads to the caller as a Houdini that is not running.
                log_error("serve_forever")

    def stop(self):
        """Stop listening and close the sockets."""
        self.running = False
        if hou.isUIAvailable():
            hou.ui.removeEventLoopCallback(self._poll)
        if self._reader is not None and self._reader is not threading.current_thread():
            self._reader.join(timeout=2.0)
        self._reader = None
        for client in list(self.clients):
            self._drop(client)
        if self.socket:
            self.socket.close()
        self.socket = None
        protocol.withdraw(self.port)
        print("HoudiniMCP server stopped")

    def _drop(self, client):
        with self._lock:
            self.clients.pop(client, None)
            self._buffers.pop(client, None)
        try:
            client.close()
        except OSError:
            pass

    # The reader thread

    def _read_loop(self):
        while self.running:
            try:
                self._read_once(0.25)
            except Exception:
                log_error("reader")
                time.sleep(0.25)

    def _read_once(self, wait):
        """Accept the new clients and read what the others sent."""
        listener = self.socket
        if listener is None:
            return
        with self._lock:
            known = list(self.clients)
        try:
            readable, _, _ = select.select([listener, *known], [], [], wait)
        except (OSError, ValueError):
            return  # a socket closed between the copy and the select
        for sock in readable:
            if sock is listener:
                self._accept()
            else:
                self._receive(sock)

    def _accept(self):
        while True:
            try:
                client, _ = self.socket.accept()
            except (BlockingIOError, OSError):
                return
            client.setblocking(False)
            with self._lock:
                self.clients[client] = []
                self._buffers[client] = b""

    def _receive(self, client):
        try:
            data = client.recv(protocol.CHUNK)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._drop(client)
            return
        with self._lock:
            if client not in self._buffers:
                return
            commands, self._buffers[client] = protocol.decode(self._buffers[client] + data)
        for command in commands:
            if command.get("type") == "interrupt":
                self._send(client, "interrupt", self._interrupt())
                continue
            with self._lock:
                if client in self.clients:
                    self.clients[client].append(command)
        if commands:
            self._wake.set()

    def _interrupt(self):
        """Stop the call that runs now. The watchdog raises the stop inside
        it, and a call that waits for the event loop reads the same file."""
        running = watchdog.current()
        path = protocol.interrupt_file(self.port)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w"):
                pass
        except OSError as error:
            return {"status": "error", "message": f"Could not ask for the stop: {error}"}
        waiting = self.waiting["name"] if self.waiting else None
        return {"status": "success",
                "result": {"stopping": running or waiting,
                           "note": None if running or waiting else "No call was running."},
                "session": {**identity_quiet(), "port": self.port}}

    # The main thread

    def _process_server(self):
        """Answer the commands that the reader took. Never blocks."""
        # A call that runs the event loop (hou.ui.waitUntil) runs this poll as
        # well: a second call must not start inside it.
        if not self.running or self.busy:
            return
        if self.waiting:
            self._resume()
        with self._lock:
            known = list(self.clients)
        for client in known:
            while not self.waiting:
                with self._lock:
                    queue = self.clients.get(client)
                    if not queue:
                        break
                    command = queue.pop(0)
                name = command.get("type", "")
                answer = self._run(name, lambda: dispatch(name, command.get("params", {})))
                if answer is None:
                    # The call waits. The commands after it wait in the queue.
                    self.waiting["client"] = client
                    return
                self._send(client, name, answer)
            if self.waiting:
                return

    def _send(self, client, name, answer):
        if client not in self.clients:
            return  # the caller went away while its call waited
        try:
            response = protocol.encode(answer)
        except Exception as error:
            # A result that cannot be written must not stop the plugin.
            # Without this, one bad value ends the session and every later
            # call reports that Houdini is not running.
            log_error(name)
            response = protocol.encode({
                "status": "error",
                "message": f"The result of '{name}' could not be sent: "
                           f"{type(error).__name__}: {error}"})
        # The socket stays non-blocking: the reader thread reads it at the
        # same time.
        view = memoryview(response)
        try:
            with self._send_lock:
                self._write(client, view)
        except OSError:
            self._drop(client)

    @staticmethod
    def _write(client, view):
        while view:
            try:
                sent = client.send(view)
            except BlockingIOError:
                select.select([], [client], [], 1.0)
                continue
            view = view[sent:]

    def _run(self, name, work):
        """Run one step of a call, and wrap its answer for the bridge. None when
        the call waits.

        Every answer names the session that made it. The scene file can change
        between two calls, so the identity is read now, not at start.
        """
        watcher = watchdog.watch(name, self.port)
        self.busy = True
        try:
            with watcher:
                result = work()
                if inspect.isgenerator(result):
                    result = self._step(name, result)
            if result is WAITING:
                return None
            answer = {"status": "success", "result": result}
        except watchdog.Stopped as stopped:
            answer = {"status": "error",
                      "message": f"'{name}' was stopped because "
                                 f"{watcher.reason or str(stopped) or 'the watchdog stopped it'}. "
                                 f"What it changed before that stays in the scene; undo "
                                 f"reverts it."}
        except Exception as error:
            # The caller gets the error; the traceback goes to a file. Printed,
            # it filled the console of Houdini with a traceback for every
            # refused call, and the user took them for errors of Houdini.
            log_error(name)
            message = f"{type(error).__name__}: {error}"
            hint = hints.hint(message)
            answer = {"status": "error",
                      "message": f"{message}\n{hint}" if hint else message}
        finally:
            self.busy = False
        self.waiting = None
        answer["session"] = {**identity(), "port": self.port}
        return answer

    def _step(self, name, generator, stop=False):
        """Run a waiting call up to its next wait.

        Karma draws the viewport only while the event loop of Houdini runs, and
        a call holds that loop, also through hou.ui.waitUntil. So a tool that
        must let Houdini draw is a generator: each `yield (seconds, done)`
        ends this step, and the poll runs the next step when done() is true or
        the seconds pass. Other calls wait until it ends.
        """
        try:
            if stop:
                seconds, done = generator.throw(
                    watchdog.Stopped("the caller interrupted it while it waited"))
            else:
                seconds, done = next(generator)
        except StopIteration as end:
            return end.value
        self.waiting = {**(self.waiting or {}), "name": name, "generator": generator,
                        "until": time.monotonic() + float(seconds), "done": done}
        return WAITING

    def _resume(self):
        waiting = self.waiting
        stop = os.path.exists(protocol.interrupt_file(self.port))
        if not stop and time.monotonic() < waiting["until"]:
            try:
                if not (waiting["done"] and waiting["done"]()):
                    return
            except Exception:
                pass  # the next step reads the same state and says what is wrong
        answer = self._run(waiting["name"],
                           lambda: self._step(waiting["name"], waiting["generator"], stop))
        if answer is not None:
            self._send(waiting["client"], waiting["name"], answer)
