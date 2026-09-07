import numpy as np
import SimpleITK as sitk


def create_demo_volume() -> tuple[sitk.Image, str]:
    """Create a synthetic CT-like phantom for UI testing."""
    z, y, x = np.mgrid[0:128, 0:192, 0:192]
    volume = np.full((128, 192, 192), -1000, dtype=np.int16)

    body = (
        ((x - 96) / 72.0) ** 2
        + ((y - 100) / 62.0) ** 2
        + ((z - 64) / 58.0) ** 2
    ) <= 1.0
    volume[body] = 35

    vertebral_body = (
        ((x - 96) / 35.0) ** 2
        + ((y - 108) / 24.0) ** 2
        + ((z - 64) / 18.0) ** 2
    ) <= 1.0
    volume[vertebral_body] = 900

    cancellous = (
        ((x - 96) / 28.0) ** 2
        + ((y - 108) / 18.0) ** 2
        + ((z - 64) / 13.0) ** 2
    ) <= 1.0
    volume[cancellous] = 300

    pedicle_l = (
        ((x - 63) / 12.0) ** 2
        + ((y - 87) / 16.0) ** 2
        + ((z - 64) / 11.0) ** 2
    ) <= 1.0
    pedicle_r = (
        ((x - 129) / 12.0) ** 2
        + ((y - 87) / 16.0) ** 2
        + ((z - 64) / 11.0) ** 2
    ) <= 1.0
    volume[pedicle_l | pedicle_r] = 1000

    spinous = (
        ((x - 96) / 9.0) ** 2
        + ((y - 58) / 28.0) ** 2
        + ((z - 64) / 9.0) ** 2
    ) <= 1.0
    volume[spinous] = 950

    image = sitk.GetImageFromArray(volume)
    image.SetSpacing((0.8, 0.8, 1.0))
    image.SetOrigin((-76.8, -76.8, -64.0))
    return image, "Synthetic CT phantom"
