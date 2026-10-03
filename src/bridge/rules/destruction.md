Destruction (RBD)

- Read the `destruction/` pages in docs before the first build
  (`destruction/overview`, `destruction/constraints`, `destruction/concrete`
  for stone, `destruction/guidedsims`).
- Clean input: closed, normals out, no intersecting pieces. A model made of
  separate overlapping meshes is joined and repaired first.
- `rbdmaterialfracture` cuts and makes the constraints. Start coarse (about
  200 pieces) and look at it in `rbdexplodedview`; add interior detail
  (`rbdinteriordetail`) and more pieces only after the motion is approved.
  Local damage: Geometry Culling.
- The outside breaks first, the inside holds. Make the outer shell weak and
  the inner structure 10-100 times stronger, or keep the core and floors
  inactive (active=0). Set the strength by ratio, not by an absolute value.
- Pieces hold until the start frame, then the bonds break. Direction beats
  physics: use a guided simulation rather than forces.
- Bullet solver: 2-4 substeps and more constraint iterations; many substeps
  only to diagnose. Let settled pieces sleep. Real scale; a big slow
  collapse gets slowed time (read the parameter name on the node page).
- Never cook a simulation in memory: not by the display flag, not by the
  playbar, not by a cook of the solver. Put the cache node right after the
  solver when you make it, write the frames to disk with `cook`
  mode "cache_write", and look only at what the cache reads back. A
  simulation in memory fills the RAM, is lost when Houdini quits, and cooks
  again on every change upstream. The same for every fracture: a File Cache
  (or rbdio) right after it, and the solver reads the cache.
- Cache RBD with rbdio, not filecache (filecache silently loses constraints
  and proxies); pyro, FLIP and Vellum with filecache. Cache order: pieces,
  then dust, then smoke. Dust is emitted from pieces with
  `length(v@v) > 3 && i@active`.
- No errors on the dopnet means nothing. Write a test cache of 20-30 frames
  and look at several frames, not one still; a long shot in parts of 100-150
  frames. Look for pieces passing through each other and pieces flying off.
- The final shot: a low camera, 28-35 mm, motion blur on.
