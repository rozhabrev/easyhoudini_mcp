Parallel renders and TOP networks
- Several renders of one scene (cameras, render settings, quality levels,
  light rigs, frame ranges) go through a TOP network, not one by one through
  `render`. Build it with `pdg` mode "render_setup": one work item per
  variant, a copy of the ROP that reads the work item attributes, and a Local
  Scheduler that runs `parallel` jobs at a time. Do not build it by hand.
- One ROP for all variants. What differs between variants lives in work item
  attributes, never in copies of the scene or of the LOP chain. A variant
  key is the real name of a parameter on the ROP: read the ROP with
  node_inspect first. On a USD Render ROP in /stage the camera is
  `override_camera` and the settings prim is `rendersettings`; on a Karma ROP
  it is `camera`. A key that names no parameter changes nothing, and
  render_setup lists it: fix it before you cook.
- Something the ROP has no parameter for (a light on or off, a material, a
  look) is a variant LOP: put it in the LOP chain with the value as an
  expression on the work item attribute (`@light_rig`, `` `@look` ``), or as
  a variant set chosen by the attribute.
- Each job opens the .hip from disk. Save before the cook; a change made
  after the save is not in the render.
- How many at once. CPU render (Karma CPU, Mantra): jobs share the cores, so
  `parallel` 2-4 with threads split between them, never one full-thread job
  per core. Karma XPU: every job loads the scene into the same GPU memory;
  start with `parallel` 1-2 and watch the memory, a third job often fails
  on a mid-size scene. Ask the user how many cores and which GPU, if you do
  not know.
- Test small first: cook one variant on one frame at low resolution (a
  variant with `resolution` or a lower `pathtracedsamples`), look at the
  picture, then cook all.
- Follow the cook with `pdg` mode "status". A failed item has a log: read it
  before changing anything. A cook that reports success with no file in the
  output folder has failed.
- Each variant writes to its own folder (output_root/<variant>/). Never two
  variants into one file name.
- When all are done, show the user one frame of each variant side by side,
  not the folder.
