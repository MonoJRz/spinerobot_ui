# Construct assessment

In Setup → Case information → Edit, tap C1–S1 blocks to choose screw levels.
Save preserves anatomical order and supports noncontiguous selections. Cervical
and S1 selections request their TotalSegmentator masks; existing T1–L5 label IDs
are preserved. Missing requested anatomy is not replaced with another level.

After screw acceptance, Construct shows rods, per-screw breach distances, and
estimated Gertzbein–Robbins categories. “Insert rods” shows/hides planned rods.
Screw colors match their grade. Collision highlighting takes precedence.

Tap “Open HU analysis” for a LEFT / VERTEBRA / RIGHT overview. Each large card
shows mean HU, **Coverage**, and a CT depth sparkline. Three levels appear per
page, with large Previous / Next buttons rather than scrolling. Profiles share a
single HU range across all planned screws, including negative and >1000 HU values.
Missing samples appear as pink crosses and gaps. Skipped sides display “SKIPPED”.
Tap a card for its full profile, histogram, numeric summaries, and review reasons.

Mean HU still averages valid depth samples from segmented bone in a 1 mm shell
outside the screw. No intensity threshold or age adjustment is applied. The former
“bone coverage” percentage is now labeled **CT sample support** in the detailed
sample readout: the fraction of shell samples that both belong to the selected
vertebra and contain finite CT values. It is not screw containment.

**Coverage** estimates the fraction of the actual screw surface inside the raw
vertebra mesh, after the same fixed entry exclusion as G–R grading. Each triangle
contributes its physical area, sampled at four equal-area subtriangle centroids;
this avoids weighting dense mesh regions more heavily simply because they have
more vertices. Closed-surface membership uses
[VTK vtkSelectEnclosedPoints](https://vtk.org/doc/nightly/html/classvtkSelectEnclosedPoints.html).
Open, nonmanifold, missing, or cropped bone geometry yields an unavailable metric,
not an assumed 0% or 100%. Values are not rescaled to a presumed elderly cohort.
This is a sampled surface-area estimate, not screw volume, bone density, fixation
strength, or clinical clearance. It still depends on segmentation accuracy and
mesh resolution; no patient-dataset validation has been performed for this change.

“REVIEW” flags a non-A/unavailable G–R result, any measured surface outside the
mesh, missing CT samples, unavailable coverage, or an assessment reason. No new HU
or coverage percentage cutoff is used. “✓ G–R A” means grade A, full sampled
containment, and a complete CT profile; it does not certify safe fixation. These
rules are available through the large Metrics button and in per-screw details.

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

The overview uses large cards, 48–52 logical pixel buttons, and numeric values
alongside color and sparklines. Detail plots support tapping and arrow keys,
Home, and End. Changing the scan or closing the overview closes its detail window.
Layout tests cover a 1024×700 overview; physical touchscreen sizing still depends
on Qt display scaling and the intended hardware.
