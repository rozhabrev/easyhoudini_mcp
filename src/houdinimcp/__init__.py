"""The HoudiniMCP plugin, which runs inside Houdini.

A GUI session starts the server from `uiready.py`, which the installer writes.
A headless session starts it from `headless.py`.

This module must import without `hou`: the bridge imports `houdinimcp.protocol`
from its own venv, outside Houdini.
"""

# The one version of the package. pyproject.toml reads it from here, and the
# plugin reports it in every answer, so the bridge sees an old plugin copy.
__version__ = "0.4.2"


def start_server():
    """Start the TCP server and keep it on hou.session."""
    import hou
    from .server import HoudiniMCPServer

    if getattr(hou.session, "houdinimcp_server", None):
        print("HoudiniMCP server is already running.")
        return hou.session.houdinimcp_server
    server = HoudiniMCPServer()
    server.start()
    hou.session.houdinimcp_server = server
    return server


def stop_server():
    """Stop the TCP server if it runs."""
    import hou

    server = getattr(hou.session, "houdinimcp_server", None)
    if not server:
        print("HoudiniMCP server is not running.")
        return
    server.stop()
    hou.session.houdinimcp_server = None
