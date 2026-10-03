Look and render (our defaults)
- The final scene is assembled in Solaris (/stage): materials, lights, camera
  and render settings live in LOPs. Do not render from /obj or /out.
- Geometry is built right in /stage in SOP Create LOPs. Do not build it in
  /obj and pull it in with a SOP Import.
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
