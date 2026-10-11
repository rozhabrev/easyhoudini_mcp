# Changelog

## 0.4.1 - 2026-10-11

From users of 0.3: after a few follow-up requests the network filled with
subnets and network boxes. The 0.3 rule "build in one subnet beside the given
node" was read as one subnet per request, and every change made a new box with
the same title, which took the nodes of the old one and left it empty. A test
of 0.4 also left the old version of a part next to the new one, wired to
nothing, and placed nodes so close that a neighbour covered a name.

### Changed
- Core rules, Where to build: before the first change of each request the
  agent reads the network it works in and changes its own earlier work there:
  the same nodes, the same chain, the same boxes. A subnet only for a whole
  task of many nodes, made once; a small change goes into the chain.
- Core rules, Build: a change the user asks for replaces what was there; the
  old version is deleted, not left beside the new one. Many like parts
  (buttons, bolts, ticks) are one part copied to points, never a node each.
- Core rules, Network order: one box for each block and one box for each
  title; look for the box before making one, delete a box that ends up empty;
  leave room for the name of a node.

### Added
- The bridge checks the structure in code (`bridge/structure.py`). Right after
  a call that makes a subnet or a network box, it warns when the scene now has
  two boxes with one title or repeated subnets. The `layout_check` of
  `scene_file` save reports, for the agent's own nodes only, nodes on one spot
  or drawn over each other (the name counts), nodes outside boxes, boxes over
  each other, empty boxes, repeated boxes and subnets, empty subnets and nodes
  wired to nothing. The user's nodes are never reported, so the agent does not
  go and move them.

### Fixed
- `layout_check` skipped every network inside a SOP Create: it sits in a
  locked asset, though its network is editable. It now checks every network
  that the user can edit.

## 0.4.0 - 2026-10-10

### Added
- Your own tools: a function in a Python file in
  `$HOUDINI_USER_PREF_DIR/easyhoudini_mcp/tools/` (or a folder in
  `HOUDINIMCP_TOOLS`), marked with `@tool`, becomes a tool that the agent can
  run through the new `custom` tool. The agent gets the list with its first
  result, and the core rules tell it to use such a tool instead of building
  the same step by hand. A run is one undo group; a changed file is read again
  without a restart. The idea comes from the toolsets of Unreal MCP.

## 0.3.1 - 2026-10-10

### Fixed
- Codex / ChatGPT desktop: the installer wrote the server command into
  `~/.codex/config.toml` as `command = "C:\Users\..."`, and TOML reads the
  backslashes of a Windows path as escapes - the app refused to start on that
  line. The command and the args are now written escaped. If your config is
  already broken: run the installer again, or open `config.toml` and replace
  the double quotes on that line with single quotes.

## 0.3.0 - 2026-10-09

From a live session: a low poly shell around a shoe, given as one node inside
a SOP Create. The agent built in /obj instead, moved the display flag of the
user, drew a procedural setup where the user asked for a shape by hand, kept
fitting without asking, hung Houdini in a VEX loop that could not be stopped
from the server, and left the Houdini console full of tracebacks.

### Rules
- The core starts with which rule wins: the words of the user in this
  request, then what was given (scene, node, path, file), then the core, then
  a topic.
- Where to build: next to the given node, in one subnet wired from it, never
  in another network without a request. The display and render flags of the
  user stay where they are.
- How procedural: procedural by default; "by hand", "from scratch", "draw it"
  mean fixed geometry (one wrangle with addpoint and addprim is fine), no
  CTRL null, no invented controls.
- Show each result and ask: a picture and two or three numbers after every
  result that is somewhat ready, then "OK, or go on, with which changes?".
  Merged with the old milestone rule.
- Topics: `need(path)` and hints in scripting, a hard limit on every while
  loop in VEX (modeling, scripting), the API guesses that fail most often.
- The server instructions no longer forbid saving: save new versions next to
  the user's file, never over it.

### Errors
- Every failed call, and every error that a result carries (execute, an item
  of a list, a batch step), goes to `errors.jsonl` in the data folder of the
  bridge, with the tool, the mode, the code of execute and the Houdini
  version. Secrets in code are hidden. `houdinimcp-bridge errors` counts the
  log by error signature.
- The same error twice in a session comes back with "This is the same error
  as N calls ago" and what to do.
- Hints for the most frequent errors of the log: a path that does not exist
  (with the nodes that are there), an unknown node type (with close names), a
  locked asset, a menu value that is not a token, an ambiguous VEX call, and
  wrong API guesses (`setDisplayFlag` on a ROP, `geometry()` on a LOP,
  `planes()` on a Copernicus COP, `inputLabel`).
- `need(path)` in execute: hou.node that fails at once with the path and its
  neighbours instead of returning None.
- The plugin no longer prints tracebacks to the Houdini console (one session
  had 140 000 lines). They go to `plugin_errors.log` in the data folder of
  Houdini. Connects and disconnects of the bridge are not printed either.
- node_inspect: mode "errors", synonyms for modes that agents guess, and the
  closest mode in the refusal of an unknown one.

### Session
- `session(action="interrupt")` goes over a new socket connection. A reader
  thread of the plugin answers it while a call holds the main thread of
  Houdini, so the stop reaches a Houdini on another machine through the
  tunnel. A plugin without the thread gets the old interrupt file.
- The bridge counts the calls that change the scene since the last save and
  says so at ten, then every five.

### Fixes
- The timelapse moves the display flag only off a node that the agent made.
  It moved the flag of a SOP Create to a new subnet, which changed what the
  stage got and started a heavy cook.
- `select(show=True)` shows the node it names; it showed the network one
  level up.
- `scene_overview` mode "node_types" reads `pattern` and takes the category in
  any case; without both it gives the counts, not 200 000 characters.
- `capture`: `frame=1` explains that it is not a frame number; renderer
  "karma" picks Karma; a camera prim path outside LOPs says how to show it.
- `node_inspect` mode "image" reads Copernicus COPs (layers, not planes).
