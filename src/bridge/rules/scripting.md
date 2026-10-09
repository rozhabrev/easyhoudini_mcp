Scripting (Python and HScript sent to Houdini)

- Python in the scene is the last resort. Nodes, parameters and wires go
  through the tools; `execute` is for what no tool does.
- Get a node with `need(path)`, not `hou.node(path)`. hou.node gives None for
  a wrong path, and the script fails three lines later with "'NoneType' object
  has no attribute ...", the most frequent error in the logs. need() fails at
  once with the path and the nodes that are there.
- A failed call can carry a `hint`: what to do about this error. Read it
  before the next try.
- A script that fails stops at the line and leaves half its changes. Before
  a retry, read what exists and create only what is missing, or you get
  duplicate nodes. Wrap one step in `hou.undos.group("Agent: <step>")`, so the
  user can undo it with one Ctrl+Z (not around a save).
- Only ASCII in VEX and Python code inside the scene: a non-Latin comment
  breaks it with an unclear error. Check VEX after you write it.
- Node type categories are capitalized: `Sop`, `Dop`, `Lop`.
- A menu parameter takes its token (`menuItems()`). In HScript compare a menu
  by index with ch(), not chs() == "token". Set the number of a multiparm
  before its entries.
- `set` does nothing on a parameter that has an expression or keys: remove
  them first (`deleteAllKeyframes`), set, then read `rawValue` back. Frame
  ranges (`$FSTART/$FEND`) on caches and flipbooks are the usual trap.
- Attribute Wrangle class: 0 Detail, 1 Primitives, 2 Points, 3 Vertices.
  addpoint and addprim only in Detail.
- A while loop in VEX or Python has a hard limit on its steps. A loop that
  never ends holds Houdini; `session(action="interrupt")` stops a Python
  loop, not a VEX cook.
- Wire a node with several outputs by index: `setInput(i, src, out_index)`.
  DOP nodes have no render flag; in a DOP merge the left input acts on the
  right ones.
- These do not exist, though agents invent them: `hou.text.vexSyntaxCheck`,
  `hou.pdg.*`, `hou.secure`, `hou.lopNetworks()`, `hou.updateGraphTick()`,
  `node.inputLabel(i)` (it is `node.inputLabels()[i]`), `setDisplayFlag` on a
  ROP, `geometry()` on a LOP (read `stage()`), `planes()` on a Copernicus COP
  (read `layer()`).
- A node inside a locked asset (inside a Karma or SOP Create LOP) refuses
  changes with PermissionError. Work next to it, or on the parameters that
  its top node shows.
  Read the `docs` page of any HOM call you have not used in this session.
- Reading a simulation from Python: `set_frame` gives stale data; cook the
  dopnet with `cook(force=True)` on the frame. Check motion over a frame
  range, not with a loop of set_frame.
- Count with intrinsics (`primitivecount`), not `len(geo.prims())`; check
  packed pieces through `packedfulltransform` and `bounds`, not a dump.
