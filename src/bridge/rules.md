How we work in Houdini

These rules come from real sessions and from the verdicts of an artist on the
results. They win over your habits. They are about the scene that you leave
behind for a person to read and change, not about which call you make.

Before you start
- Work in a saved scene with a real path, never in untitled. Save a new version
  before a render, a long cook or a simulation, and never write over an old one.
- The timelapse records your work (capture mode "timelapse"). Send renders
  through `render`, so the timelapse keeps a copy. Renders go to files, not
  to MPlay.
- Ask if the task needs a simulation at all. A keyframed or procedural motion
  is often cheaper and easier to direct.

Build
- Measure first. Put every important number (heights, radii, counts, angles)
  on one CTRL null as spare parameters, and reference them with ch(). Units
  are metres.
- Blockout first: grey forms, silhouette and proportions. Show them, get an OK,
  then add detail, then materials.
- Place each part from the real bounding box of its neighbour, never from a
  guessed offset. At the end, look for parts left at the origin.
- Build a repeated element once (column, arch, bay) and copy it to points. One
  CTRL parameter changes the count.
- Model a turned element (column, baluster, vase, leg) by revolving a profile:
  base with a transition, a shaft that tapers to the top, a capital, smooth
  joins. A stack of cylinders reads as "a bar with lumps on it" and is a
  failure.
- Use a ready node when one does the job. Use VEX for complex parametric
  geometry that nodes make awkward; prefer simple nodes otherwise. Inside the
  scene logic is VEX; Python is for files and the outside world.
- One wrangle does one step (one sets the attributes, the next applies them),
  so the user can bypass and recombine them by hand.
- Fuse after each merge and boolean. Boolean fails on touching or coplanar
  parts: join those through VDB.
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
- One numbered network box per stage (`01_REFERENCE`, `02_BLOCKOUT`, ...).
- Colours: green OUT_, blue inputs and imports, yellow CTRL, purple caches,
  red broken, grey parked. Dot nodes only for long wires.
- Write a comment on a node that reads another node by a path: a path has no
  wire, and nobody sees it.

Check
- "The command ran" proves nothing. Read the values back, read the errors, and
  look at the picture (capture returns it to you). Look from several sides:
  the main view, a three-quarter view, and grey without materials.
- To compare with a photo, first estimate its focal length and angle, and put
  a camera there with the same frame shape. Fit the camera, not the geometry.
  Name the differences from the largest: camera, silhouette, proportions,
  depth, detail, material. Never write just "matches".
- After a fix, compare before and after, and confirm that each fix you claim
  is visible.
- After each stage, look at the cook times. Replace a slow step with a fast
  one: a for-each loop, a simpler shape, a blast instead of a boolean, less
  geometry earlier in the chain.
- Three tries on one detail, or the same error three times: stop and show
  what you tried and what each try showed. Do not switch method in silence.
- Use honest labels: "matches photo 3 from this angle", "ready for
  simulation", not "done".
- Stop often and ask the human. When the human is not at Houdini, send what
  they can judge without it: pictures from several angles, an exploded view,
  a wireframe for topology, a picture of the node graph.

Live session
- Do not touch the mouse or the screen of the machine.
- A timeout is not a failure: Houdini still cooks, and a new call waits behind
  it. Send a tiny call first (the current frame), then decide.
- A script that fails stops halfway and leaves half its changes. Before a
  retry, read what exists, or you get duplicate nodes.
- Only ASCII in VEX and Python code inside the scene.
- No full topology audit of a model with millions of polygons: check by parts.
  Warn before anything that can take more than a minute.
- While a simulation is in the displayed chain, do not jump far on the
  timeline.

Destruction (RBD)
- Read the `destruction/` pages in docs before the first build.
- Clean input: closed, normals out, no intersecting pieces.
- Start coarse (about 200 pieces) and look at the motion; add interior detail
  only after the motion is approved.
- The outside breaks first, the inside holds. Make the outer shell weak and
  the inner structure 10-100 times stronger, or keep the core and floors
  inactive (active=0). Set the strength by ratio, not by an absolute value.
- Pieces hold until the start frame, then the bonds break. Direction beats
  physics: use a guided simulation rather than forces.
- No errors on the dopnet means nothing. Cook 20-30 frames and look at several
  frames, not one still. Cache RBD with rbdio. Cache order: pieces, then dust,
  then smoke.
