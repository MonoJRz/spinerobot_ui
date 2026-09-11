# BART Spine — level-by-level pedicle screw planning upgrade

This ZIP is an **overlay package for the current `MonoJRz/spinerobot_ui` `feat/segmentation` branch**. It intentionally contains only new/replaced files, so it can be reviewed and copied over your current checkout without replacing unrelated work.

## What changed

- Reads **Region / levels of interest** from Setup (for example `L3 – L5`).
- Builds the workflow in anatomical order: **superior → inferior, left → right**.
- Focuses the three MPR views near the active posterolateral vertebral region.
- `MARK ENTRY POINT` changes the MPR cursor to a crosshair; click one MPR view to define the entry point.
- Automatically estimates a first-pass trajectory from the selected vertebral segmentation.
- Constrains the trajectory to the estimated vertebral **endplate plane** using a PCA-derived superior/inferior axis.
- Ray/mask intersection estimates the available anterior depth.
- Radial mask clearance along the posterior part of the ray estimates a rough pedicle width.
- Snaps the first-pass recommendation to standard screw diameter/length values.
- Displays the active screw in **all MPR views and 3D**. Accepted/non-active screws remain visible in 3D.
- Adds a compact **floating 72 px bottom screw-size tray** over the MPR workspace. The sliders are intentionally narrow; numeric spin boxes provide precise edits.
- Saves plans beside the CT at `planning/pedicle_screws.json` in LPS millimetres.

## Apply to your branch

```bash
cd ~/Workspace/spinerobot_ui
git switch feat/segmentation

# Optional safety snapshot
git status
git add -A && git commit -m "checkpoint before planning workflow upgrade"

# Unzip this package over the repository root
unzip -o ~/Downloads/spinerobot_planning_upgrade.zip -d ~/Workspace/spinerobot_ui

source .venv/bin/activate
pip install -e .
bart-spine-ui
```

If your ZIP downloads somewhere else, change only the ZIP path in the `unzip` command.

## Test workflow

1. Open **Setup** and load the clinical CT.
2. In Case Information, set `Region` (for example `L3 – L5`). The current default `L3 – L5` is also forwarded to Planning on startup.
3. Open **Planning**.
4. Run or load TotalSegmentator. Existing `segmentation/vertebrae_*.nii.gz` masks are reused as before.
5. Planning starts at the most superior requested level, **LEFT** side.
6. Click **MARK ENTRY POINT**, then click the posterior cortical entry point in an MPR view.
7. Review the cyan screw projection in MPR and the simple cylinder + larger head in 3D.
8. Adjust diameter/length in the floating bottom tray if needed.
9. Click **ACCEPT & NEXT**. The queue advances left → right, then to the next inferior level.
10. Inspect `planning/pedicle_screws.json` beside the CT/segmentation folder.

## Run the included tests

```bash
source .venv/bin/activate
pytest -q tests/test_planning_service.py
```

## Important algorithm note

This is a **research prototype / first-pass geometric planner**, not a clinically validated pedicle screw planning system. The automatic trajectory and size recommendation must be visually reviewed and manually corrected. The current endplate constraint first fits a thin superior/anterior vertebral-body surface band with PCA, falls back to the whole-vertebra superior/inferior axis when needed, and projects the screw direction into that estimated endplate plane. A later version should segment/fit the actual superior endplate and explicitly validate cortical breach, canal/foramen distance, and pedicle containment before clinical use.
