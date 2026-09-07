# Architecture

## Goal

Keep the surgical workstation modular enough to grow from a four-view CT prototype into:

```text
Imaging
  ↓
Segmentation
  ↓
Pedicle Screw Planning
  ↓
Registration
  ↓
Robot Setup
  ↓
Navigation / Execution
```

without coupling the robot to Qt widgets or tying planning mathematics to VTK actors.

## Layers

```text
┌───────────────────────────────────────────────────────────┐
│ UI / Workflow Pages                                      │
│ ImagingPage · future PlanningPage · RegistrationPage ... │
├───────────────────────────────────────────────────────────┤
│ Controllers                                              │
│ ImagingController · future PlanningController ...        │
├───────────────────────────────────────────────────────────┤
│ Domain / Services                                        │
│ ImagingService · planning geometry · registration math   │
├───────────────────────────────────────────────────────────┤
│ Adapters                                                 │
│ SimpleITK · VTK · future NDI · ROS 2 · xArm             │
└───────────────────────────────────────────────────────────┘
```

### UI

Responsibilities:
- buttons, panels, dialogs
- presentation
- connect user intent to controllers
- show controller state/errors

Do **not**:
- parse DICOM
- compute registration
- implement screw geometry
- call robot services directly

### Controllers

Responsibilities:
- coordinate a workflow
- expose Qt signals/events to the UI
- call services
- own transient workflow state

Examples:
- `ImagingController`
- future `PlanningController`
- future `RegistrationController`
- future `NavigationController`

### Domain/services

Responsibilities:
- algorithms and state that should remain testable without the GUI
- image loading
- screw geometry
- transformations
- registration metrics
- navigation error calculations

### Visualization

VTK-specific rendering belongs under `visualization/`.

Keep:
- CT data
- screw trajectory definition
- registration transforms

separate from:
- `vtkActor`
- `vtkRenderer`
- camera state

This is important because the same planned trajectory may need to be rendered in three MPRs,
3D, logged to a file, and sent to ROS 2.

## Coordinate convention

The starter canonicalizes medical image data to **LPS** because DICOM/ITK naturally use LPS.

Never assume that a point coming from another subsystem is LPS.

At every boundary make the convention explicit:

```text
DICOM / SimpleITK        LPS
Internal medical volume  LPS

3D Slicer interoperability  often RAS
ROS / robot frames          explicitly named TF frame
NDI                         tracker-defined frame
```

Conversion helpers already exist in:

```text
bart_spine_ui.core.coordinates
```

For registration/navigation, upgrade from loose arrays to named transform objects before
connecting hardware.

## Workflow extension pattern

A major procedure stage should be implemented as:

```text
features/planning/
    models.py
    geometry.py
    service.py

controllers/
    planning_controller.py

ui/pages/
    planning_page.py
```

`PlanningPage` then subclasses `WorkflowPage` and is registered with `WorkflowShell`.

The base MPR workspace can be reused rather than copied.

## Future long-running jobs

Do not run these on the Qt GUI thread:

- TotalSegmentator
- large DICOM indexing
- surface extraction
- ICP / optimization
- ROS network waits
- NDI connection/reconnection

Put them behind a controller and use worker threads/processes.
