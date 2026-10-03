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

USD pipeline (studio practice)
These come from Pixar, Animal Logic (ALab), NVIDIA and SideFX. They fill in
"Scene structure (USD)" above and never override it.
- Fixed top level: geometry under `/world`, one prim per part
  (`/world/island`, `/world/tower`), cameras in `/cameras`, lights in
  `/lights`, shot materials in `/materials`, render settings under `/Render`.
  Nothing loose at the root. Set Import Path Prefix of every SOP Create to its
  real place (`/world/<part>`), never the default `/$OS`; no prim may end up
  as `/sopcreate1/mesh_0`. Turn on Set Default Primitive.
- Prim names: ASCII letters, digits and `_`, not starting with a digit, lower
  snake_case, padded numbers (`rock_01`). No spaces, `-`, `.`, `:` or
  Cyrillic. The prim of a part has the name of its network block.
- Kinds: each cached part root is `component`, `/world` and grouping prims are
  `group` or `assembly`, never a component inside a component
  (`subcomponent`). Configure Primitives fixes the kind hierarchy.
- Count prims, not polygons: one mesh per piece that has its own transform or
  material. Per-face materials go through GeomSubsets (SOP groups ->
  Subset Groups), not split meshes. Check the prim count after each import.
- A heavy part gets a light proxy: `<part>/geo/render` (purpose render) and
  `<part>/geo/proxy` (purpose proxy, one reduced mesh). Proxy vs render is
  purpose, not a variant. Variants only for real alternatives, always with a
  default selection.
- Static stays static: for a still part, Topology Attributes = Static and no
  time samples. After an animated SOP Create put a Cache LOP over the frame
  range, so the graph below it does not recook every frame.
- Every written layer has defaultPrim, `metersPerUnit` 1 and `upAxis` Y
  (Configure Layer). Data in `.usd`/usdc, keep the USD ROP output processor
  Use Relative Paths, never an absolute disk path inside a layer. Never
  overwrite a cache the final graph reads: write `<part>_v002.usd`.
- Bring a part that adds new prims in with a Reference (Reference Primitive =
  Default Primitive) at `/world/<part>`. Bring a cache that changes prims
  which already exist (a simulation over the layout) in with a Sublayer above
  the layer it changes. Payload (Reference Type = Payload File) only on the
  root of a heavy part: never on groups, never nested, never on light parts.
- Change a loaded cache with `over` edits, never re-create the prim, and keep
  prim paths stable: a renamed prim silently drops every override on it. A
  graph that loads caches only to edit them: Layer Break after the loads and
  Strip Layers Above Layer Breaks on the ROP, so the file holds only the edits.
- Repeats go to USD as instances, not copies of the mesh. Up to a few hundred
  objects a person may move by hand: Copy to Points LOP, Method = Instanceable
  Reference. Mass scatter (grass, stones, debris): a PointInstancer; in SOP
  Create pack the pieces, Packed Primitives = Create PointInstancer,
  `s@usdinstancerpath` on the points, `s@name` on each prototype. The
  prototype list is fixed over the whole range: include every prototype from
  the first frame. Vary the look by primvars, not variants. Never edit under
  an instance; edit the instance prim itself.
- Light animation in one file with time samples. A heavy or long cache: one
  file per frame (`$F4` in the path, Flush Data After Each Frame), assembled
  with a Geometry Clip Sequence LOP. Never sublayer a `$F4` sequence. Volumes:
  one `.vdb` per frame from a File Cache SOP, read with a Volume LOP.
- Motion blur needs data: points and changing topology carry `v` (and `w`
  for spin); constant topology needs two time samples across the shutter.
- The light block starts its own layer (Configure Layer, Start New Layer).
  Link lights with the Light Linker, do not move lights to hide them.
