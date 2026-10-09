"""The log of every failed call, and the memory of the errors of this session.

Each error of a tool goes to one JSON line in `errors.jsonl` in the data folder
of the bridge: which tool and mode, the error, the code that execute ran. The
log is the input for the next fix: `houdinimcp-bridge errors` counts the
errors by their signature, and the ones that come back most often are the
ones to fix in code.

The bridge also remembers the signatures of this session. An agent that
gets the same error twice is guessing, and the answer to the second one says
so.
"""
import collections
import json
import os
import re
import sys
import time

from houdinimcp import protocol

LOG_NAME = "errors.jsonl"
MAX_BYTES = 5 * 1024 * 1024   # one old file is kept: errors.jsonl.1
CODE_CHARS = 2000
MESSAGE_CHARS = 2000

# A key or a password in a script must not reach a log file.
_SECRET = re.compile(r"(?i)\b(api[_-]?key|token|secret|password|passwd|authorization)"
                     r"(\s*[=:]\s*)(['\"]?)[^\s'\",)]+")

_state = {"calls": 0, "seen": {}}


def log_path() -> str:
    return os.path.join(protocol.data_dir(), LOG_NAME)


def signature(message: str) -> str:
    """The error without the parts that change from call to call: the names
    in quotes and the numbers. Two errors with one signature are one bug."""
    found = re.findall(r"([A-Za-z]+(?:Error|Exception|Failed))[:\s]+([^\n\"\\]{0,90})",
                       message or "")
    if found:
        kind, text = found[-1]
        return f"{kind}: " + re.sub(r"'[^']*'", "'X'", re.sub(r"\d+", "N", text)).strip()
    return "other: " + re.sub(r"\d+", "N", (message or "").strip())[:90]


def _scrub(text):
    return _SECRET.sub(r"\1\2\3<hidden>", text) if text else text


def tick() -> int:
    """Count one call of a tool. Returns its number in this session."""
    _state["calls"] += 1
    return _state["calls"]


def record(tool: str, message: str, mode: str = None, code: str = None,
           version: str = None) -> str:
    """Write one error to the log. Returns a note for the caller when the same
    error came back in this session, or an empty text."""
    sig = signature(message)
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": tool, "mode": mode,
             "type": sig.split(":", 1)[0], "signature": sig,
             "message": _scrub((message or "")[:MESSAGE_CHARS]),
             "code": _scrub(code[:CODE_CHARS]) if isinstance(code, str) else None,
             "houdini": version}
    _write(entry)
    key = (tool, sig)
    before = _state["seen"].get(key)
    _state["seen"][key] = _state["calls"]
    if before is None:
        return ""
    ago = _state["calls"] - before
    return (f"This is the same error as {ago} call{'s' if ago != 1 else ''} ago. Stop "
            f"guessing: read the docs page of the node or the call (docs tool), then try "
            f"once more. On a third failure, stop and show the user what you tried.")


def _write(entry):
    path = log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if os.path.exists(path) and os.path.getsize(path) > MAX_BYTES:
            os.replace(path, path + ".1")
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass  # a log that cannot be written must not fail the call


def soft_errors(result) -> list:
    """The errors that a result reports without failing the call: execute
    answers {"executed": false, "error": ...}, a list of items carries an
    "error" in an item, a batch names the step that stopped it."""
    texts = [result] if isinstance(result, str) else [
        part for part in (result or []) if isinstance(part, str)]
    found = []
    for text in texts:
        try:
            data = json.loads(text)
        except (TypeError, ValueError):
            continue
        _collect(data, found, depth=0)
    return found


def _collect(data, found, depth):
    if depth > 3:
        return
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, str) and error:
            found.append(error)
        for key in ("nodes", "items", "results", "failed"):
            for item in data.get(key) or []:
                _collect(item, found, depth + 1)
        if isinstance(data.get("result"), dict):
            _collect(data["result"], found, depth + 1)


def summary(path: str = None, top: int = 30) -> list:
    """The errors in the log, counted by tool and signature, most frequent
    first, each with its last example."""
    counts = collections.Counter()
    example = {}
    for name in (path or log_path()) + ".1", path or log_path():
        try:
            with open(name, encoding="utf-8") as handle:
                lines = handle.readlines()
        except OSError:
            continue
        for line in lines:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            key = (entry.get("tool"), entry.get("signature"))
            counts[key] += 1
            example[key] = entry
    return [{"count": count, "tool": key[0], "signature": key[1],
             "mode": example[key].get("mode"), "last": example[key].get("time"),
             "example": (example[key].get("message") or "")[:300]}
            for key, count in counts.most_common(top)]


def cli(argv=None):
    """`houdinimcp-bridge errors [top]`: the most frequent errors in the log."""
    argv = sys.argv[2:] if argv is None else argv
    top = int(argv[0]) if argv and argv[0].isdigit() else 30
    rows = summary(top=top)
    if not rows:
        print(f"No errors in {log_path()}.")
        return
    print(f"{log_path()}: the {len(rows)} most frequent errors")
    for row in rows:
        print(f"{row['count']:5d}  {row['tool']}{'/' + row['mode'] if row['mode'] else ''}"
              f"  {row['signature']}")
        print(f"       last {row['last']}: {row['example'][:160]}")
