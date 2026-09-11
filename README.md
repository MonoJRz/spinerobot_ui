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
spinerobot_ui/
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
cd ~/Workspace/spinerobot_ui

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

## Run in Docker on Ubuntu with NVIDIA GPU and X11

The container includes BART Spine UI, PySide6, VTK, SimpleITK, PyTorch, and
TotalSegmentator. The selected host directory is mounted read-write at `/data`;
the file picker opens there, and generated masks are written back to the same
host directory under `segmentation/`.

Host prerequisites:

- Ubuntu graphical session using X11 or XWayland
- Docker Engine with the Compose v2 plugin
- NVIDIA driver and NVIDIA Container Toolkit configured for Docker
- `xauth` (`sudo apt install xauth`)

Confirm GPU access before building the application image:

```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

If Docker reports permission denied for `/var/run/docker.sock`, add the current
user to the Docker group, then log out and back in (group membership grants
root-equivalent Docker access):

```bash
sudo usermod -aG docker "$USER"
newgrp docker
docker run --rm hello-world
```

Then launch BART Spine UI with the directory containing the CT file or DICOM
case directories:

```bash
./run-docker.sh /absolute/path/to/medical-data
```

`docker compose build` can also be run separately. Runtime mount variables have
safe build-only defaults, so that command does not require CT or X11 paths.

The script builds the image when necessary, grants the container only the
current X11 authorization cookie, runs it with the host user UID/GID, and mounts:

```text
host medical-data directory -> /data                  (read/write)
host X11 socket             -> /tmp/.X11-unix        (read-only)
temporary Xauthority file   -> /tmp/bart-spine.xauth (read-only)
~/.cache/bart-spine-ui      -> /cache                 (read/write)
```

TotalSegmentator model weights are downloaded on the first segmentation and
persist in `~/.cache/bart-spine-ui`. The container reserves all NVIDIA GPUs and
16 GB of shared memory. To pin a different official TotalSegmentator base image:

```bash
TOTALSEGMENTATOR_IMAGE=wasserth/totalsegmentator:2.11.0 \
  ./run-docker.sh /absolute/path/to/medical-data
```

Segmentation output ownership matches the Ubuntu user that launched the script.

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

### ROS2 and NDI status

For the native UI with the sibling `spinerobot_ros2` workspace built, run
`./run-ui.sh` (or `bart_ui` on the lab workstation). This sources ROS Jazzy and
that workspace before starting the UI, using ROS domain 42.

Start NDI with `../spinerobot_ros2/launchers/start_ndi.sh`, or from the robot
console. The setup page receives `/tracking/status`: NDI connection is based on
heartbeat arrival, while tool, robot, and patient markers require visible,
valid, fresh status. After one second without updates, the connection shows
“No heartbeat” and stale markers become “Not tracked”. Occluded markers do not
disconnect the NDI system. Only one process should own the tracker serial port.
