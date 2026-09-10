from __future__ import annotations

from importlib.resources import files
from pathlib import Path

SUPPORTED_DIAMETERS_MM = (3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0)
SUPPORTED_LENGTHS_MM = (20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100)

HEAD_DIAMETER_MM = 13.0
HEAD_HEIGHT_MM = 15.0
TULIP_SLOT_WIDTH_MM = 6.0
ROD_SEAT_OFFSET_MM = 10.5
GENERIC_ROD_DIAMETER_MM = 5.5


def _match(value: float, allowed: tuple[float, ...] | tuple[int, ...], name: str):
    value = float(value)
    nearest = min(allowed, key=lambda item: abs(float(item) - value))
    if abs(float(nearest) - value) > 1e-6:
        raise ValueError(
            f"Unsupported {name} {value:g} mm. "
            f"Supported values: {', '.join(str(v) for v in allowed)}"
        )
    return nearest


def screw_asset_path(diameter_mm: float, length_mm: float) -> Path:
    d = float(_match(diameter_mm, SUPPORTED_DIAMETERS_MM, "diameter"))
    length = int(_match(length_mm, SUPPORTED_LENGTHS_MM, "length"))
    d_token = f"{d:.1f}".replace(".", "p")
    return Path(
        files(__package__)
        / "assets"
        / "screws"
        / f"screw_D{d_token}_L{length:03d}.stl"
    )


def tulip_asset_path() -> Path:
    return Path(
        files(__package__)
        / "assets"
        / "tulip"
        / "tulip_head.stl"
    )
