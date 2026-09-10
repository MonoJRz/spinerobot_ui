# BART Spine Implant Models v0.1.0

Generic **visualization** models for the BART Spine planning UI.

This package was matched to the current `feat/planning` dimensions:

- Screw diameter: **3.0–10.0 mm**, step **0.5 mm**
- Screw length: **20–100 mm**, step **5 mm**
- Prebuilt screw shafts: **255**
- Tulip outer diameter: **13.0 mm**
- Tulip height: **15.0 mm**
- Tulip U-slot width: **6.0 mm**
- Generic rod diameter used to shape the slot: **5.5 mm**
- Rod-seat center offset: **10.5 mm** from entry, opposite the screw direction

## Important design choice

The **screw shaft and tulip are separate STL meshes and separate VTK actors**.

The screw is fixed to the planned trajectory. The tulip shares the same shank axis
but can rotate around that axis so its U-slot follows the planned rod tangent.

Local model frame:

- Origin: pedicle entry point / distal tulip plane
- `+Z`: screw direction, entry -> tip
- `+X`: tulip U-slot / rod direction
- `+Y`: across the slot
- Screw extends into `+Z`
- Tulip extends into `-Z`

This matches the current BART planning logic, where the rod seat is at
`entry - direction * (0.70 * HEAD_HEIGHT_MM)`.

## Install

From this extracted directory:

```bash
source .venv/bin/activate
pip install -e .
```

Then:

```python
from bart_spine_implant_models import assembly_actors

slot_direction = None
if rod_plan is not None:
    slot_direction = rod_plan.tulip_slot_directions_lps.get(plan.level)

screw_actor, tulip_actor = assembly_actors(
    plan,
    rod_slot_direction_lps=slot_direction,
)

renderer.AddActor(screw_actor)
renderer.AddActor(tulip_actor)
```

## Why the tulip is independent

Do **not** bake the tulip into each screw STL. A polyaxial head must be able to
rotate about the screw shank to follow the local rod tangent. The helper projects
the requested rod direction into the plane normal to the shank, matching the
mechanically realizable orientation already used in `planning/rod.py`.

## Planning/collision use

These meshes are intended for **visualization and UI rendering**. The thread form is
generic and deliberately lightweight. For pedicle-wall breach, clearance, collision,
or safety calculations, continue to use the nominal screw envelope defined by
`diameter_mm` and `length_mm`, rather than individual thread triangles.

## Assets

`src/bart_spine_implant_models/assets/screws/`
contains every supported diameter/length combination.

`src/bart_spine_implant_models/assets/tulip/tulip_head.stl`
is the independent tulip model.

`assets/manifest.json` documents the dimensions and coordinate frame.

## Research-use note

This is a generic model and does not reproduce any manufacturer's implant geometry.
It is not a manufacturing model and should not be treated as a regulatory-validated
implant definition.
