# BART Spine UI Starter

A standalone medical-imaging UI foundation for the BART Spine Robot project.

This project intentionally does **not** require 3D Slicer at runtime. It keeps the successful
standalone architecture from the prototype:

- **PySide6** — application shell and workflow UI
- **VTK** — MPR and 3D rendering
- **SimpleITK** — medical image / DICOM loading
- **NumPy** — geometry and future planning mathematics

The package is structured so screw planning, registration, tracking, robot control, and
navigation can be added as independent features instead of accumulating inside one large UI file.

## Current working functionality

- NIfTI / NRRD / MetaImage loading
- DICOM series folder loading
- synthetic demo phantom
- real-time axial MPR
- real-time coronal MPR
- real-time sagittal MPR
- interactive 3D volume rendering
- CT-oriented window/level and 3D transfer-function presets
- fixed Red / 3D / Green / Yellow layout
- installable Python package and CLI entry point

## Project layout

```text
bart_spine_ui_starter/
├── pyproject.toml
├── requirements.txt
├── run.py
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEVELOPMENT.md
│   └── ROADMAP.md
├── src/
│   └── bart_spine_ui/
│       ├── application.py
│       ├── core/
│       │   ├── coordinates.py
│       │   └── types.py
│       ├── imaging/
│       │   ├── conversion.py
│       │   ├── demo.py
│       │   ├── io.py
│       │   ├── models.py
│       │   ├── presets.py
│       │   └── service.py
│       ├── controllers/
│       │   └── imaging_controller.py
│       ├── visualization/
│       │   ├── mpr.py
│       │   ├── volume3d.py
│       │   └── workspace.py
│       ├── ui/
│       │   ├── main_window.py
│       │   ├── workflow_shell.py
│       │   └── pages/
│       │       └── imaging_page.py
│       └── workflows/
│           ├── base.py
│           └── registry.py
└── tests/
    ├── test_coordinates.py
    └── test_demo_volume.py
```

## Install

```bash
cd ~/bart_spine_ui_starter

python3 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
pip install -e .
```

For development tools:

```bash
pip install -e ".[dev]"
```

If Qt reports missing XCB packages on Ubuntu 24.04:

```bash
sudo apt update

sudo apt install -y \
  libxcb-cursor0 \
  libxcb-xinerama0 \
  libxkbcommon-x11-0 \
  libxcb-icccm4 \
  libxcb-image0 \
  libxcb-keysyms1 \
  libxcb-randr0 \
  libxcb-render-util0 \
  libxcb-shape0 \
  libxcb-xfixes0
```

## Run

After `pip install -e .`:

```bash
bart-spine-ui
```

or:

```bash
python -m bart_spine_ui
```

or, without remembering the package command:

```bash
python run.py
```

The application starts with the synthetic CT phantom so the viewer can always be checked before
loading clinical data.

## Design rule

**UI widgets do not load DICOM, planning code does not manipulate Qt widgets, and robot code
must not depend on VTK rendering.**

Keep dependencies flowing inward:

```text
UI
 ↓
Controllers / Workflows
 ↓
Core + Services
 ↓
Imaging / Planning / Registration / Robot adapters
```

See `docs/ARCHITECTURE.md` before adding major features.
