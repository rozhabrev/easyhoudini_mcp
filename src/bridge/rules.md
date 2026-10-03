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
- Every block sits in a network box with a plain title of what it is
  (`03_COLUMNS`, `04_TREES`, `07_FRACTURE`). Every node you create gets its
  own place: lay out each batch of new nodes right after you build it, never
  leave nodes at the origin or on top of each other. Before you finish, check
  that no two nodes share a position and no node is outside a box.
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

Scene structure (USD)
- Build to USD standards in /stage, in two graphs side by side. The test
  graph: each part is built in its own SOP Create and checked statically in
  the stage (one frame, how it looks and renders), never played back there.
  When a part is approved, write it to USD from right there (a USD ROP after
  the SOP Create, to $HIP/usd/<part>.usd) and bring that file into the final
  graph with a Reference or Sublayer LOP. The final graph reads only caches,
  so it plays fast.
- Destruction, ocean, hair, feathers and crowds go to the render through the
  Houdini Procedural LOPs (`houdinirbdprocedural` and its siblings): cache
  the simulation points, not animated geometry. Read
  `solaris/houdini_rbd_procedural` first: it needs `path`, `name` and
  `piecename` set up exactly as described there.
- One COP network `textures` for the whole scene; group its chains in
  network boxes by material.

Look and render (our defaults)
- The final scene is assembled in Solaris (/stage): materials, lights, camera
  and render settings live in LOPs. Do not render from /obj or /out.
- Simple geometry (low poly, blockouts, product shots) is built right in
  /stage in a SOP Create LOP. Do not build it in /obj and pull it in with a
  SOP Import. Heavy SOP work (simulations, caches) may stay in /obj.
- Main LOP chain: geometry -> material library -> merge_lights -> camera ->
  render. Lights are a separate block on the side (each light its own node,
  or a short chain of lights) that comes into the main chain through a Merge
  LOP named `merge_lights`. Never put lights in line with the geometry.
- Every material is a Karma Material Builder, inside a Material Library LOP.
  Never put loose shader nodes straight into the library. Create it the way
  the TAB tool does:
  `voptoolutils._setupMtlXBuilderSubnet(destination_node=<matlib>,
  name=<mat>, mask=voptoolutils.KARMAMTLX_TAB_MASK,
  folder_label='Karma Material Builder', render_context='kma')`.
  Inside you get `inputs`, `mtlxstandard_surface`, `mtlxdisplacement`,
  `material_properties` (kma_material_properties) and
  `Material_Outputs_and_AOVs` (surface, displacement, properties). Keep this
  standard. Wire textures into the surface, height into mtlxdisplacement, and
  use material_properties when the look needs it. Delete none of these nodes.
- Textures are made by you in COPs, never downloaded or photo textures.
  Create a COP Network LOP (`copnet`) inside /stage, name it `textures`, dive
  in, build one chain per map. Each chain ends in a null
  `OUT_<material>_<map>` (`OUT_grass_basecolor`). A material reads it with a
  MtlX Tiled Image (or MtlX Image) whose File is `op:` plus the path to that
  null, no space: `op:/stage/textures/OUT_grass_basecolor`. Karma renders it
  live, no files to bake. The geometry needs good UVs.
- Render setup is the Karma (Setup) tool of Houdini 22, three nodes:
  `karmarendersettings` (karmarenderproperties::2.0) -> `renderpass`
  (Render Source = set, `chs("../karmarendersettings/primpath")`) ->
  `usdrender_rop` (Render Pass = `chs("../renderpass1/primpath")`,
  husk_instantshutter = `1 - ch("../karmarendersettings/enablemblur")`).
  Set camera, resolution, output path and the engine on the settings node.
- Render with Karma XPU unless the task says otherwise. Render to files in
  $HIP/render/<name>/, check several frames by eye, no black or empty frames.
- "Stylized", "low poly", "hand-painted" means: flat facets, simple bold
  colours with soft painted variation, no photoreal detail. Keep it so in
  geometry, textures and light.
- Light it like a product shot: a warm key sun with soft shadows, a sky or
  dome for fill, a clean light background. Frame the whole subject.
- An animation that ends in a render needs a camera set before the
  simulation: you check the motion through it, not only from the default
  view.
- When you are not sure how SideFX builds a standard setup, create it with
  their own tool or preset, read what it made, and follow that.

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
