How we work in Houdini

These rules come from real sessions and from the verdicts of an artist on the
results. They win over your habits. They are about the scene that you leave
behind for a person to read and change, not about which call you make.

This is the core. The detail for each kind of work is in a topic: read it with
the `rules` tool before you start that kind of work (see Topics below). What
the user asks for in the prompt wins over a rule: "build it in /obj" or
"download the textures" means exactly that.

Show your work on screen
Houdini does not follow you. Work done through tools and scripts never moves
the panes: the network editor stays on the network the person left open, the
viewer keeps drawing the old display node. A person watching the screen, or
the timelapse, then sees nothing from the first call to the final render. So:
- At the start of each stage, open the network you build in:
  `select(paths=[<first node of the stage>], show=True)`. It opens that
  network in the network editor, frames the nodes, and points the viewer at it.
- After each stage, show its result: `select(paths=[<OUT_ or last node>],
  show=True, display=True)`, so the viewer draws what you just made, framed.
  In /stage the display flag goes on the last LOP of the stage. Inside a SOP
  Create the display flag is its output: put it only on the end of the chain,
  and to look at a node in the middle use show without display.
- Do this as part of the stage, not at the end: the steps between are what the
  recording is for. Several small visible steps beat one big invisible script.

Before you build: what you must know
Five things decide the scene. Take each from the prompt, the attached
pictures, the open scene and earlier turns first.
1. What to build, and from what: a reference (photo, drawing, sizes) or a
   description precise enough to model from.
2. The result: a still render, a turntable, an animation, a simulation.
   Ask if the task needs a simulation at all: keyframed or procedural motion
   is often cheaper and easier to direct.
3. The look: stylized or realistic, and how finished (blockout, model,
   lookdev, final render).
4. The scale: real size in metres, or how big next to something known.
5. Where the scene lives: a saved .hip with a real path.
If one of these is missing and the answer changes what you build, ask before
the first node. Ask once, in one message, at most three questions, each with
two to four labelled options and your default first ("Style: a) stylized low
poly (default) b) realistic"). Never ask what has a sane default (units,
renderer, node names, colours of boxes): take the default and say which one
you took. Never ask a question that the docs answer.

When to stop and ask, when to look it up
- A fact about Houdini (a node, a parameter, a menu token, a HOM call, how a
  setup is wired): read the `docs` tool. Never guess a name, never ask the
  user for it. When you are not sure how SideFX builds a standard setup,
  create it with their own tool or preset, read what it made, and follow
  that.
- A question of intent or taste (what it should look like, how much, which
  of two readings of the prompt): ask the user. Do not build both.
- Two tries on one thing with no new information from the second, or the
  same error twice: stop guessing. Read the docs page of the node, then try
  once more. Still failing on the third try: stop, show the user what you
  tried and what each try showed, and offer two or three ways on with your
  pick. Do not switch method in silence, and never rebuild from scratch to
  get past an error.
- Before anything that deletes work, overwrites a file or can cook for more
  than a minute: say so and wait for a yes.
- At each milestone (blockout, model, look, first sim frames, render) show
  pictures and wait for an OK before the next one. When the user is not at
  Houdini, send what they can judge without it: pictures from several angles,
  an exploded view, a wireframe for topology, a picture of the node graph.
- When the user has said "do it without me", keep going through milestones,
  but still stop on the third failed try.

Topics
Read a topic with the `rules` tool before its kind of work, once per session.
- `modeling`: modeling from references or a description, blockout, repeats,
  turned shapes, booleans.
- `usd`: anything in /stage: stage layout, prim names, kinds, references and
  payloads, instancing, caches. Read it with `look` before the first LOP.
- `look`: materials, COP textures, lights, camera, Karma render setup.
- `destruction`: RBD fracture, constraints, the bullet solver, its caches.
- `scripting`: before `execute` or any Python or HScript sent to Houdini.

Before you start
- Work in a saved scene with a real path, never in untitled. Save a new version
  before a render, a long cook or a simulation, and never write over an old one.
- The timelapse records your work (capture mode "timelapse"). Send renders
  through `render`, so the timelapse keeps a copy. Renders go to files, not
  to MPlay.
- On a scene you did not make, check its health first: bypassed nodes,
  unconnected inputs, branches that lead nowhere, nodes with zero points.

Build
- Measure first. Put every important number (heights, radii, counts, angles)
  on one CTRL null as spare parameters, and reference them with ch(). Units
  are metres.
- Blockout first: grey forms, silhouette and proportions. Show them, get an OK,
  then add detail, then materials.
- Nodes first, VEX last. Select a part with a node (Group by normal
  direction, bounding box or object, Group Expression), then change it with a
  node (Mountain, Peak, Soft Transform, Smooth, Transform) limited to that
  group. Example: a ragged bottom on a tube is Group by normal (0,-1,0) plus
  Mountain on that group, not a wrangle. Points come from Scatter, Circle,
  Line or Copy, profiles from Curve or Line, names from Name, UVs from UV
  Project, UV Flatten or a triplanar in the material.
- VEX only when no node does the job, and then procedural: read ch() and
  relative measures (relbbox, getbbox), never fixed coordinates or point
  numbers (`@P.y < -0.3` breaks as soon as a size changes). Never paste the
  same wrangle twice: build it once and reuse its output. Inside the scene
  logic is VEX; Python is for files and the outside world.
- One wrangle does one step (one sets the attributes, the next applies them),
  so the user can bypass and recombine them by hand.
- Work non-destructively: try a variant in a new branch through a switch,
  bypass instead of delete. Fix forward, one thing at a time. Before you delete
  a node, search the string parameters for references to it.
- Never rewrite the network from scratch in the middle of a task, and add
  nothing that was not asked for.

Network order
- All labels in English: node names, boxes, comments. Sticky notes may use the
  language of the user; keep them short, black with white text.
- Main chain on the left, branches on the right. Lay out only the nodes you
  made, never the whole network.
- Name nodes by meaning, lowercase with underscores (`fracture_low_tier`).
  Prefix the nodes you make with `ai` and the step number: `ai03_fracture`.
- The network is made of blocks. A block ends in a null `OUT_<what>`; the next
  block starts with an object_merge of that OUT_. No long trees, no wires
  across blocks.
- Every block sits in a network box with a plain title of what it is
  (`03_COLUMNS`, `04_TREES`, `07_FRACTURE`). Every node you create gets its
  own place: lay out each batch of new nodes right after you build it, never
  leave nodes at the origin or on top of each other. Before you finish, check
  that no two nodes share a position and no node is outside a box
  (`scene_file` save reports both as `layout_check`; it must be empty).
- Colours: green OUT_, blue inputs and imports, yellow CTRL, purple caches,
  red broken, grey parked. Dot nodes only for long wires.
- Write a comment on a node that reads another node by a path: a path has no
  wire, and nobody sees it.

Check
- "The command ran" proves nothing. Read the values back, read the errors, and
  look at the picture (capture returns it to you). Look from several sides:
  the main view, a three-quarter view, and grey without materials.
- A cook time of 0.0 s means it did not cook. A cache button that "finishes"
  in a blink may have written nothing: check that the files exist and are not
  empty.
- After each structural step, measure against the reference: heights,
  diameters, angles, counts. A wrong scale is the most common silent error.
- After a fix, compare before and after, and confirm that each fix you claim
  is visible.
- After each stage, look at the cook times. Replace a slow step with a fast
  one: a for-each loop, a simpler shape, a blast instead of a boolean, less
  geometry earlier in the chain. Keep a polygon budget and say it.
- Use honest labels: "matches photo 3 from this angle", "ready for
  simulation", not "done".

Live session
- Do not touch the mouse or the screen of the machine.
- A timeout is not a failure: Houdini still cooks, and a new call waits behind
  it. Send a tiny call first (the current frame), then decide. A closed
  connection means Houdini quit: reopen the last saved version yourself.
- No full topology audit of a model with millions of polygons: check by parts.
- While a simulation is in the displayed chain, do not jump far on the
  timeline. Keep the display flag on a node without a simulation.
