# Development Guide

## First setup

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
```

Run:

```bash
bart-spine-ui
```

Tests:

```bash
pytest
```

Static checks:

```bash
ruff check src tests
```

## Rules for adding code

### 1. Keep `MainWindow` small

`MainWindow` should only build the application shell, register workflow pages, and provide
application-level status.

### 2. Put image loading in `imaging/`

Do not call `sitk.ReadImage()` from a Qt widget.

### 3. Put VTK rendering in `visualization/`

Do not expose VTK actors as the source of truth for planning data.

### 4. Represent surgical plans as data first

Future screw plan example:

```python
@dataclass
class ScrewPlan:
    vertebral_level: str
    side: str
    entry_lps_mm: np.ndarray
    target_lps_mm: np.ndarray
    diameter_mm: float
    length_mm: float
```

The MPR and 3D views should render this object.

### 5. Use explicit transforms

Prefer names such as:

```text
T_patient_from_ct
T_tracker_from_patient
T_robot_base_from_tracker
T_tool_from_flange
```

instead of unnamed 4×4 matrices.

### 6. Do not block the UI

Long processing must move behind worker tasks.

## Suggested feature package pattern

When screw planning begins:

```text
src/bart_spine_ui/
├── planning/
│   ├── __init__.py
│   ├── models.py
│   ├── geometry.py
│   ├── service.py
│   └── validation.py
├── controllers/
│   └── planning_controller.py
└── ui/pages/
    └── planning_page.py
```

When NDI/robot development begins, keep hardware drivers separate:

```text
src/bart_spine_ui/
├── tracking/
│   ├── ndi_client.py
│   └── models.py
└── robot/
    ├── client.py
    ├── models.py
    └── safety.py
```

Eventually these may become ROS 2 packages, while this repository stays the workstation UI.
