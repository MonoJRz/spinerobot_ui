# Recommended Roadmap

## Milestone 1 — Viewer foundation
Current starter.

- [x] standalone Qt application
- [x] axial/coronal/sagittal MPR
- [x] real-time sliders
- [x] 3D CT rendering
- [x] DICOM / volume loading
- [x] modular package structure

## Milestone 2 — Medical viewer interaction

- [ ] shared patient-space crosshair
- [ ] click in one MPR to update all views
- [ ] mouse-wheel slice scrolling
- [ ] linked window/level
- [ ] zoom/pan controls
- [ ] L/R, A/P, S/I orientation annotations
- [ ] 3D crosshair / slice plane visualization

## Milestone 3 — Spine segmentation

- [ ] TotalSegmentator service
- [ ] background worker execution
- [ ] vertebral level selection
- [ ] segmentation overlay in MPR
- [ ] vertebra surface in 3D
- [ ] visibility/opacity controls

## Milestone 4 — Pedicle screw planning

- [ ] `ScrewPlan` domain model
- [ ] entry + target point editing
- [ ] screw STL / procedural screw visualization
- [ ] screw length and diameter
- [ ] axial/sagittal trajectory angles
- [ ] trajectory-aligned oblique MPR
- [ ] perpendicular cross-sectional MPR
- [ ] cortical breach / margin measurements
- [ ] save/load plans

## Milestone 5 — Registration

- [ ] patient/CT registration model
- [ ] surface point collection
- [ ] registration solver
- [ ] FRE / TRE-style validation metrics
- [ ] transform visualization
- [ ] registration workflow page

## Milestone 6 — Tracking / robot

- [ ] NDI client adapter
- [ ] transform graph
- [ ] ROS 2 bridge/client
- [ ] xArm status/control
- [ ] 4-DOF platform status/control
- [ ] safety state machine

## Milestone 7 — Navigation

- [ ] planned vs tracked trajectory
- [ ] entry-point error
- [ ] angular error
- [ ] depth error
- [ ] guidance UI
- [ ] procedure logging
