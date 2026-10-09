Modeling

From references
- Study the references before the first node. For each photo: where it was
  taken from, a rough focal length, what it shows. Then one list for the
  whole object: tiers, counts of columns and arches, directions, what is
  hidden or unclear. Official measurements are the truth; a number read from
  a photo is an assumption, and you say so.
- Work out every height and radius from the measurements before you build,
  and put them on the CTRL null.
- Cameras for the photos are a step of their own: estimate the focal length
  and the angle of each photo, and put a camera there with the same frame
  shape, so the verticals and the silhouette fall on the photo. Fit the
  camera, not the geometry: never bend the model to one photo. Keep three or
  four photos from different sides for the comparison.
- Compare and name the differences from the largest: camera, silhouette,
  proportions, depth, detail, material. Fix only the top three. Never write
  just "matches".

Shapes
- Place each part from the real bounding box of its neighbour, never from a
  guessed offset. At the end, look for parts left at the origin.
- Build a repeated element once (column, arch, bay) and copy it to points.
  One CTRL parameter changes the count. The count on a ring is
  round(circumference / width of one bay), the ring is points on a `circle`,
  `copytopoints` packs and instances.
- Model a turned element (column, baluster, vase, leg) by revolving a profile:
  base with a transition, a shaft that tapers to the top, a capital, smooth
  joins. A stack of cylinders reads as "a bar with lumps on it" and is a
  failure.
- In the procedural mode (the default), never build geometry in VEX. A
  building is boxes and cylinders: polyextrude, boolean for openings, clip.
  By hand (the core, How procedural), one wrangle with addpoint and addprim
  at worked-out coordinates is the right tool.
- Every while loop in VEX gets a hard limit on its steps
  (`int guard = 0; while (more && guard++ < 10000)`). A walk along a contour
  that runs past its last point never ends, and Houdini hangs until it is
  killed.
- Fuse after each merge and boolean. Boolean fails on touching or coplanar
  parts: join those through VDB.
- A global change of the whole object (a tilt, a bend) is the last transform,
  driven from a CTRL parameter.
- The block outputs are named nulls: `OUT_TOWER`, `OUT_FRACTURED`,
  `OUT_COLLISION`. Downstream reads only `OUT_*`.
