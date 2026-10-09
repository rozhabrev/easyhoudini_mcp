"""Run code inside the Houdini session."""
import io
import os
import sys
import time
import traceback
from contextlib import redirect_stdout, redirect_stderr

import hou

from .. import hints, protocol, watchdog
from . import parameters

LIMIT = 20_000


class _Live(io.StringIO):
    """Keeps what a script prints, and writes it to a file as it comes, so a
    caller that cannot wait for the answer can read the progress."""

    def __init__(self, path):
        super().__init__()
        self.path, self.flushed = path, 0.0
        try:
            self.file = open(path, "w", encoding="utf-8") if path else None
        except OSError:
            self.file = None

    def write(self, text):
        if self.file:
            self.file.write(text)
            if time.monotonic() - self.flushed > 0.5:
                self.file.flush()
                self.flushed = time.monotonic()
        return super().write(text)

    def close_file(self):
        if self.file:
            self.file.close()


class _Writes:
    """Watch the parameter writes of a script.

    A script writes parameters with `hou.Parm.set`, `hou.ParmTuple.set` and
    `hou.OpNode.setParms`, and Houdini reports none of the writes that change
    nothing or change another node. While the script runs, these three calls
    go through a wrapper that keeps one line for each such write.

    The creation script of a new node writes its own parameters. Those writes
    are not the script's, so they are not reported.
    """

    def __enter__(self):
        self.notes = {}
        self.creating = 0
        self.saved = (hou.Parm.set, hou.ParmTuple.set, hou.OpNode.setParms,
                      hou.Node.createNode)
        parm_set, tuple_set, set_parms, create_node = self.saved
        note = self.note

        def watched_create_node(node, *rest, **named):
            self.creating += 1
            try:
                return create_node(node, *rest, **named)
            finally:
                self.creating -= 1

        def watched_parm_set(parm, value, *rest, **named):
            target = parameters._referenced(parm)
            result = parm_set(parm, value, *rest, **named)
            note(parm, value, target)
            return result

        def watched_tuple_set(parm_tuple, values, *rest, **named):
            targets = [parameters._referenced(parm) for parm in parm_tuple]
            result = tuple_set(parm_tuple, values, *rest, **named)
            for parm, value, target in zip(parm_tuple, values, targets):
                note(parm, value, target)
            return result

        def watched_set_parms(node, values, *rest, **named):
            parms = {name: node.parm(name) for name in values}
            targets = {name: parm and parameters._referenced(parm)
                       for name, parm in parms.items()}
            result = set_parms(node, values, *rest, **named)
            for name, parm in parms.items():
                if parm:
                    note(parm, values[name], targets[name])
            return result

        hou.Parm.set, hou.ParmTuple.set = watched_parm_set, watched_tuple_set
        hou.OpNode.setParms = watched_set_parms
        hou.Node.createNode = watched_create_node
        return self

    def note(self, parm, value, target):
        # ponytail: checks every write; a loop of many thousand writes pays for
        # it, so cache per parameter path if that shows up.
        if self.creating:
            return
        try:
            line = parameters.script_write_note(parm, value, target)
        except hou.Error:
            return
        if line:
            self.notes[parm.path()] = line
        else:
            self.notes.pop(parm.path(), None)

    def __exit__(self, *error):
        hou.Parm.set, hou.ParmTuple.set, hou.OpNode.setParms, hou.Node.createNode =             self.saved
        return False


def execute_code(code, allow_dangerous=True, file=None, globals=None, args=None,
                 timeout=None):
    """Run Python inside Houdini and report what it printed.

    `file` runs a script that Houdini reads from disk, so a script that runs
    again with other values does not travel through the conversation twice. It
    runs as it would from a shell: `__file__` is its path, `__name__` is
    "__main__", and `args` are in `sys.argv[1:]`.
    `globals` is a dictionary of names that exist before the script runs.
    `timeout` is the budget in seconds. When it is spent the script stops where
    it is, and the answer says where, so Houdini comes back by itself.
    """
    if file:
        if not os.path.isfile(file):
            raise ValueError(f"There is no file at {file}. Houdini reads this path, so it "
                             f"must exist on the machine that runs Houdini.")
        with open(file, encoding="utf-8") as handle:
            code = handle.read()
    if not code:
        raise ValueError("Give source, the code to run, or file, a path to a script.")

    server = getattr(hou.session, "houdinimcp_server", None)
    stdout_capture = _Live(protocol.output_file(server.port) if server else None)
    stderr_capture = io.StringIO()
    name = file or "<execute>"
    namespace = {"hou": hou, "need": hints.need, "__name__": "__main__", **(globals or {})}
    if file:
        namespace["__file__"] = file
    argv = sys.argv
    sys.argv = [name] + [str(arg) for arg in args or ()]
    failed = stopped = hint = None
    watchdog.budget(timeout)
    writes = _Writes()
    try:
        with writes, redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            exec(compile(code, name, "exec"), namespace)
    except watchdog.Stopped:
        stopped = watchdog.handled()
        failed = f"Stopped, because {stopped}. Here is where it was:\n{traceback.format_exc()}"
    except Exception as error:
        # The output that came before the error is often the whole answer, so
        # it goes back with the error instead of being lost with it. The
        # traceback goes to the caller only: printed, it filled the console of
        # Houdini with one traceback for every failed script.
        failed = f"{type(error).__name__}: {error}\n{_script_traceback(error)}"
        hint = hints.hint(failed, code)
    finally:
        sys.argv = argv
        stdout_capture.close_file()

    report = {
        "executed": failed is None,
        **_cut("stdout", stdout_capture.getvalue()),
        **_cut("stderr", stderr_capture.getvalue()),
    }
    if file:
        report["file"] = file
    if globals:
        report["globals"] = sorted(globals)
    if writes.notes:
        # The last write to each parameter decides, so a write that a later
        # one repairs is not listed.
        report["write_warnings"] = list(writes.notes.values())
    if stopped:
        report["stopped"] = (f"{stopped}. What the script changed before it stopped stays "
                             f"in the scene. Give a larger timeout, or background=true, "
                             f"for long work.")
    if failed:
        report["error"] = failed
    if hint:
        report["hint"] = hint
    return report


def _script_traceback(error):
    """The traceback from the first line of the script on: the frame of this
    module says nothing to the caller."""
    frames = traceback.extract_tb(error.__traceback__)
    ours = [index for index, frame in enumerate(frames) if frame.filename == __file__]
    frames = frames[ours[-1] + 1:] if ours else frames
    return "Traceback (most recent call last):\n" + "".join(traceback.format_list(frames))


def _cut(name, text):
    """Keep the start and the end of a long output.

    A client drops a result that is too large, and then the whole call is lost.
    The middle is what a caller needs least.
    """
    if len(text) <= LIMIT:
        return {name: text}
    half = LIMIT // 2
    removed = len(text) - LIMIT
    return {name: f"{text[:half]}\n\n...[{removed} characters and "
                  f"{text.count(chr(10), half, len(text) - half)} lines removed: print "
                  f"less, or write the result to a file]...\n\n{text[-half:]}",
            f"{name}_characters": len(text)}


def execute_hscript(command):
    """Execute an HScript command and return the output."""
    result = hou.hscript(command)
    return {"stdout": result[0], "stderr": result[1]}


def evaluate_expression(expression, language="hscript"):
    """Evaluate a Houdini expression and return the result."""
    if language == "python":
        result = hou.expressionGlobals()
        val = eval(expression, result)
    else:
        val = hou.hscriptExpression(expression)
    return {"expression": expression, "result": str(val), "language": language}


def get_env_variable(name):
    """Get a Houdini environment variable ($HIP, $JOB, etc.)."""
    val = hou.getenv(name)
    return {"name": name, "value": val}
