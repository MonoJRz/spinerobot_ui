from pathlib import Path

from bart_spine_implant_models import (
    SUPPORTED_DIAMETERS_MM,
    SUPPORTED_LENGTHS_MM,
    screw_asset_path,
    tulip_asset_path,
)


def test_all_assets_exist():
    for d in SUPPORTED_DIAMETERS_MM:
        for length in SUPPORTED_LENGTHS_MM:
            assert Path(screw_asset_path(d, length)).is_file()
    assert Path(tulip_asset_path()).is_file()
