"""custom — the tools that the person wrote for their own work."""
from typing import Any, Dict

from ..connection import call_json


def tool(mode: str = "list", name: str = None, params: Dict[str, Any] = None) -> str:
    """List or run the tools that the person wrote themselves.

    A person, a studio or a course can add their own steps as Python files in
    a tools folder of their Houdini. Such a tool is their way of doing a step:
    when one fits the task, use it instead of building the same thing by hand,
    and do not rebuild what it made.

    mode: "list" (default) returns every custom tool with its description and
    arguments, the folders that are read, and the files that failed to load.
    Call it once at the start of a session. "run" calls one tool.

    name: with "run", the tool to call, as "list" names it.
    params: with "run", its arguments as an object, by the names that "list"
    gives. A wrong or missing argument is refused with the right ones.

    A run that changes the scene is one undo group. Files are read again when
    they change, so a tool edited during the session works without a restart.

    How to write one (tell the person when they ask): a .py file in
    `$HOUDINI_USER_PREF_DIR/easyhoudini_mcp/tools/` or in a folder named in
    the environment variable HOUDINIMCP_TOOLS:

        from houdinimcp.custom import tool

        @tool
        def my_step(parent: str = "/obj", count: int = 10) -> dict:
            '''What it does and when to use it. The agent reads this.'''
            ...

    @tool(mutates=False) marks a tool that only reads the scene.

    Returns JSON.
    """
    if mode == "run":
        return call_json("custom", {"mode": "run", "name": name, "params": params or {}},
                         timeout=600.0, label=f"custom tool '{name}'")
    return call_json("custom", {"mode": mode})
