from bart_spine_ui.imaging.demo import create_demo_volume


def test_demo_volume_geometry():
    image, name = create_demo_volume()

    assert image.GetSize() == (192, 192, 128)
    assert image.GetSpacing() == (0.8, 0.8, 1.0)
    assert name
