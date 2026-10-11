"""session — which Houdini answers, and start, choose, stop or interrupt one."""
import json

from .. import update
from ..connection import (HoudiniError, attach, call, detach, installs, interrupt,
                          last_session, live_sessions, start_gui, start_headless, start_hint, status,
                          stop_headless)


def tool(action: str = "status", hip: str = None, port: int = None,
         version: str = None) -> str:
    """Report the Houdini sessions, choose one, or start, stop or interrupt one.

    Use it first when a tool says that Houdini is not reachable, and use it to
    learn the Houdini version before you use an API that changed between
    releases.

    Several Houdini sessions can listen at the same time: the graphical one that
    holds the work of the user, and a headless one for your own tests. Every
    tool result names the session that answered, in `_session`. Read that line
    when a scene looks empty or wrong: an empty scene is usually the wrong
    session, not a lost scene.

    Do not use it to read the scene: scene_overview does that.

    action:
        "status"    — the session that the bridge talks to now, the other
                      sessions, the port, and the versions of the bridge, the
                      plugin and the latest release. Starts nothing, and
                      always answers.
        "list"      — every Houdini that runs, with its version, its process
                      id, its .hip file, whether it has a window and whether it
                      answers; and the Houdini versions installed.
        "attach"    — send every later command to the Houdini on `port`. Use it
                      when "list" shows more than one.
        "detach"    — forget the attached port and let the bridge choose again.
        "interrupt" — stop the call that runs now in the attached Houdini, or
                      in the one on `port`: a script past its budget, a loop
                      that will not end. Houdini answers again after it.
        "start"     — start a headless Houdini (hython) and attach to it.
                      `version` chooses the release, for example "21.0" or
                      "21.0.829"; without it, the version of the Houdini window
                      that runs. A Houdini that already runs is not touched, so
                      this is the safe way to test while a person works.
        "start_gui" — start Houdini with its window and wait for the plugin to
                      answer, up to 4 minutes. It opens the .hip file at `hip`
                      when you give one, it stays open when the bridge stops,
                      and the bridge attaches to it. `version` as for "start".
        "stop"      — stop the headless Houdini that this bridge started. A
                      Houdini that you started yourself, or with "start_gui", is
                      not touched.

    Returns JSON. The report says what to do next when nothing answers.
    """
    if action == "list":
        return json.dumps({"sessions": live_sessions(), "installed": installs()},
                          indent=2, default=str)

    # The action runs before anything reads the connection: the connection is
    # what these actions repair, so a broken one must not block them.
    done = None
    if action == "start":
        done = start_headless(version)
    elif action == "start_gui":
        done = start_gui(hip, version)
    elif action == "attach":
        if not port:
            return "action 'attach' needs a port. Call action='list' to see the ports."
        done = attach(port)
    elif action == "detach":
        done = detach()
    elif action == "interrupt":
        done = interrupt(port)
    elif action == "stop":
        done = stop_headless()
    elif action != "status":
        return (f"Unknown action '{action}'. Use 'status', 'list', 'attach', 'detach', "
                f"'interrupt', 'start', 'start_gui' or 'stop'.")

    houdini = None
    first = status()
    if first["port_is_listening"]:
        try:
            houdini = call("session", {}, timeout=15)
        except HoudiniError as error:
            houdini = str(error)
    # Read after the call, so the report shows the connection that call made.
    report = status()
    if done is not None:
        report["action"] = done
    report["mcp_version"] = update.report(last_session())
    if houdini is not None:
        report["houdini"] = houdini
    elif "problem" not in report:
        report["next_action"] = start_hint()
    return json.dumps(report, indent=2, default=str)
