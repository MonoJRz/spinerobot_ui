# Construct assessment

In Setup → Case information → Edit, tap C1–S1 blocks to choose screw levels.
Save preserves anatomical order and supports noncontiguous selections. Cervical
and S1 selections request their TotalSegmentator masks; existing T1–L5 label IDs
are preserved. Missing requested anatomy is not replaced with another level.

After screw acceptance, Construct shows rods, per-screw breach distances, and
estimated Gertzbein–Robbins categories. “Insert rods” shows/hides planned rods.
Screw colors match their grade. Collision highlighting takes precedence.

Tap “Show CT values · HU” to display entry-to-tip density strips for calibrated
CT data. A matching gradient legend labels 0, 250, 500, 750, and 1000 HU; gray
has a separate “No sample” key. Tap or drag a strip for a persistent depth, mean
HU, and bone sampling coverage readout. Arrow keys, Home, and End also select
samples. The fixed
0–1000 HU display scale clips colors only; numerical values are not clipped.
Gray means no valid bone samples. Sampling does not infer osteoporosis or
convert HU into calibrated bone mineral density.

## Geometry and limits

Grading follows [BART_Planning GradeStep.py](https://github.com/BARTLAB-MU/BART_Planning/blob/bacec64fde3204255387be08eccf36d1f6ec335e/BARTPedicleScrewSimulatorWizard/GradeStep.py): actual transformed screw mesh, segmentation coverage first, fully outside triangles only, then maximum nearest-surface distance. G–R thresholds are inclusive: B ≤2, C ≤4, D ≤6, E >6 mm; complete absence of segmentation coverage is E.

The first 10 mm remain excluded as requested, instead of copying the reference's asset-specific local-Y head crop. Mesh points probe the selected vertebra's binary mask with trilinear interpolation. Positive coverage is inside; only triangles whose vertices all have zero coverage are measured. This deliberately suppresses small boundary crossings; it can also miss small breaches on mixed triangles. Boundary contact with no fully outside triangles is shown as ungraded, not the reference's fallback E.

Distances use the raw 0.5 label isosurface in physical LPS coordinates. This retains the application's boundary rather than assuming Slicer's closed-surface smoothing is identical. The reference merges all segments; this implementation uses the selected vertebra to avoid counting contact with a neighboring bone as containment. These differences mean results are similar, not guaranteed identical.

The red line is the true-scale distance between the maximum outside screw-mesh point and its nearest bone point. Locate breach shows the exact raw bone and clipped screw mesh; Full construct restores the smoothed overview. The depth from entry is reported separately. Distances below the smallest voxel spacing remain flagged. Missing data stays unavailable. HU shell sampling is unchanged.

The C1–S1 selector extends level and segmentation support, not clinical validation
of the existing trajectory estimator for cervical or sacral anatomy.

Tests use synthetic solids with known breach distances and linear CT intensity
fields, including anisotropic spacing and rotated image axes. UI tests exercise
selection persistence, HU visibility, rod toggling, and scan reset behavior.

## Touchscreen interaction

The density toggle uses a full-width, 56 logical pixel touch area. Color is supplemented by explicit values and state
labels. HU values are available on tap, without relying on hover tooltips.
The Qt display scaling and physical touchscreen should still be checked on the
intended hardware.

Design references: [Google touch-target guidance](https://support.google.com/accessibility/android/answer/7101858?hl=en-GB)
(48 dp minimum and spacing) and [NN/g touchscreen targets](https://www.nngroup.com/articles/touch-target-size/)
(physical size, separation, and visible affordances).
