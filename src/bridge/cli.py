"""The entry point: build the MCP server and run it on stdio."""
from contextlib import asynccontextmanager
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from . import connection, tools

INSTRUCTIONS = """\nThese tools are few on purpose. Each one takes a `mode` and a set of arguments,
and bends to the task instead of being replaced by a script. Read the
description of the tool before you write code: almost every script that agents
write by hand is one mode of one tool here. `execute` is the last resort, not
the first.

Every tool takes one item or a list of them, so a list is one call, not many.

The tools
  session          which Houdini answers; attach to one, start a headless one
  scene_overview   the lists: nodes, objects, cameras, materials, caches
  node_inspect     everything about a node: type, parms, inputs, flags, errors
  node_edit        make, name, move, flag, delete
  connect          wire nodes, break a wire, change input order
  parm_set         write parameters, press buttons, expressions, keyframes
  geometry_inspect what a node cooked: points, prims, attributes, volumes
  cook             compute over frames, write a cache, reset a simulation
  console          what Houdini said, and which nodes hold errors
  capture          a picture of the viewport, and the state of the window
  docs             the official Houdini documentation
  playbar          the current frame, the frame range, playback
  render           ROP nodes: make one, start it, follow the work
  scene_file       the .hip file on disk
  select           which nodes are selected
  hda              digital assets: what is installed, what is inside one
  stage_inspect    the USD stage that a LOP node makes
  pdg              TOP networks and their work items
  batch            several calls in one round trip and one undo group
  execute          run code in the session. Last resort.

Houdini fails without an error more often than it fails with one. These facts
cause most wrong results.

1. A parameter write can report success and change nothing: the parameter
   carries an expression or a keyframe, another parameter disables or hides
   it, or a strict range clamps the value. parm_set says so, and execute lists
   such writes in `write_warnings`. Read them.
2. A parameter that reads another node through a channel reference writes to
   that other node, also through `hou.Parm.set` in execute. parm_set refuses
   such a write until you ask for it with follow_reference.
3. A node name gets a numeric suffix when the name is already used. Keep the
   path that the create call returned. Do not look the node up by the name you
   asked for.
4. A cook error hides behind an empty geometry result. geometry_inspect reads
   the errors and the warnings and reports them.
5. A solver keeps its result. After any change inside a Pyro, FLIP, Vellum or
   RBD solver, call cook with mode "sim_reset", or the node gives the old
   result back with no error.
6. The display flag and the render flag are different flags.
7. Inspect before you assume. Confirm a node type, a parameter name, a VEX
   function or a `hou` call with the `docs` tool or in the live session. Do not
   answer from memory about the Houdini API.

Rules of the house

- Do not lay out the user's network, and never call `layoutChildren` in
  execute. node_edit and connect place each node you make under its inputs;
  a layout of a whole network moves work the user placed by hand. Read
  node_inspect mode "layout" on the network after you add nodes.
- The VEX you write stays in the scene, and the user reads it and tunes it by
  hand. Write it for that reader.
  - Name things with plain words in camelCase: `outwardSpeed`, `distanceToShell`.
    Never one letter, and never a niche term where two plain words say it.
  - Keep the values between steps as attributes (`f@distanceToSkin`,
    `v@outwardDirection`), so the user can see them in the spreadsheet. Use a
    local variable only when the user asks for one.
  - One clear condition, or an if/else. Never two mirrored `if` lines. One
    comment above each block that says what the block is for.
  - In a Gas Field Wrangle, an `@` binding that is not in "Fields to Write to"
    (`exportlist`) is read-only, and the snippet fails at the first cook with
    "Read-only expression on left side of assignment". When your snippet writes
    a temporary field, put its name in `exportlist`, or set `exportlist` to `*`.
- Do not save the user's .hip file unless you are asked to.
"""


# How the scene is built and checked. It lives in its own file so that a
# person can read and change it without reading code.
RULES = Path(__file__).with_name("rules.md").read_text(encoding="utf-8")


@asynccontextmanager
async def lifespan(server):
    yield {}
    connection.shutdown()


def build() -> MCPServer:
    return MCPServer("HoudiniMCP", instructions=INSTRUCTIONS + "\n" + RULES, lifespan=lifespan,
                     tools=tools.build(RULES))


def main():
    build().run(transport="stdio")
