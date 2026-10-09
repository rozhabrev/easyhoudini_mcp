"""Stop a call that runs past its time budget, or that the caller asks to stop.

A call runs on the main thread of Houdini, and while it runs Houdini answers
nothing: not the bridge, not the user. One careless script must not cost the
user the scene, so one thread watches the call that runs now and raises
`Stopped` inside it when its budget is spent, or when the bridge writes the
interrupt file of this port (session action='interrupt').

The exception arrives at the next Python step. A single long call into Houdini
(one cook, one iterPoints on a huge geometry) finishes first.
"""
import ctypes
import os
import threading
import time

from . import protocol

POLL_SECONDS = 0.25
RETRY_SECONDS = 2.0


class Stopped(BaseException):
    """Raised inside a call that the watchdog stops.

    A BaseException, like KeyboardInterrupt, so a script that catches every
    Exception cannot swallow it.
    """


_lock = threading.Lock()
_current = None   # the call that runs now; see watch.__enter__
_thread = None


def start():
    """Start the watching thread once for this process."""
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_watch, name="houdinimcp-watchdog", daemon=True)
        _thread.start()


class watch:
    """Mark the call that runs now, so the watchdog can stop it."""

    def __init__(self, command, port):
        self.command, self.port = command, port
        self.reason = None

    def __enter__(self):
        global _current
        _remove(protocol.interrupt_file(self.port))
        with _lock:
            _current = {"thread": threading.get_ident(), "command": self.command,
                        "started": time.monotonic(), "budget": None, "port": self.port,
                        "reason": None, "fired": None, "handled": False}
        return self

    def __exit__(self, *error):
        global _current
        # The exception can arrive while this runs. Clear the record and any
        # exception that is still pending, or it fires later, outside the call.
        while True:
            try:
                with _lock:
                    if _current and _current["reason"]:
                        self.reason = _current["reason"]
                        ctypes.pythonapi.PyThreadState_SetAsyncExc(
                            ctypes.c_ulong(_current["thread"]), None)
                    _current = None
                return False
            except Stopped:
                continue


def current():
    """The name of the call that runs now, or None."""
    with _lock:
        return _current["command"] if _current else None


def budget(seconds):
    """Give the call that runs now a time budget, counted from now."""
    with _lock:
        if _current and seconds:
            _current["budget"] = time.monotonic() - _current["started"] + float(seconds)


def handled():
    """The call caught Stopped and is on its way out: raise it no more.
    Returns why the watchdog stopped it."""
    with _lock:
        if not _current:
            return None
        _current["handled"] = True
        return _current["reason"]


def _watch():
    while True:
        time.sleep(POLL_SECONDS)
        with _lock:
            if not _current:
                continue
            elapsed = time.monotonic() - _current["started"]
            why = None
            if os.path.exists(protocol.interrupt_file(_current["port"])):
                _remove(protocol.interrupt_file(_current["port"]))
                why = f"the caller interrupted it after {elapsed:.1f} seconds"
            elif _current["budget"] and elapsed > _current["budget"]:
                why = f"it ran {elapsed:.0f} seconds, past its time budget"
            if _current["reason"]:
                # Raised again when the first one did not end the call: a
                # script that catches BaseException must still come back.
                if _current["handled"] or time.monotonic() - _current["fired"] < RETRY_SECONDS:
                    continue
            elif why is None:
                continue
            _current["reason"] = _current["reason"] or why
            _current["fired"] = time.monotonic()
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_ulong(_current["thread"]), ctypes.py_object(Stopped))


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass
