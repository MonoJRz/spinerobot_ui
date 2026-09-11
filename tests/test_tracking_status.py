"""NDI heartbeat and marker freshness must be independent of robot traffic."""
import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication
from spinerobot_interfaces.msg import TrackingStatus

from bart_spine_ui.robot.ros_client import RobotRosClient
from bart_spine_ui.ui.setup_right_sidebar import SetupRightSidebar


@pytest.fixture
def client():
    app = QApplication.instance() or QApplication([])
    client = RobotRosClient()
    assert client._node is not None
    assert client._node.context.get_domain_id() == 42
    yield client
    client.shutdown()
    app.processEvents()


def status(frame="patient_marker", visible=True, valid=True, age=0.0):
    return TrackingStatus(frame_id=frame, visible=visible, valid=valid, age_sec=age)


def test_occlusion_keeps_ndi_online_and_updates_setup(client):
    sidebar = SetupRightSidebar()
    client.tracking_connection_changed.connect(sidebar.set_tracking_connected)
    client.marker_changed.connect(lambda frame, tracked: sidebar.set_patient_marker_tracked(tracked))
    client._on_tracking_status(status(visible=False, valid=False))
    assert "Connected" in sidebar.tracking_status.text()
    assert "Not tracked" in sidebar.patient_status.text()
    client._on_tracking_status(status())
    assert "Connected" in sidebar.patient_status.text()
    sidebar.close()


def test_timeout_without_robot_messages_and_recovery(client):
    connections = []
    client.tracking_connection_changed.connect(connections.append)
    with patch("bart_spine_ui.robot.ros_client.time.monotonic", return_value=100):
        client._on_tracking_status(status())
    with patch("bart_spine_ui.robot.ros_client.time.monotonic", return_value=102):
        client._check_connection()
    assert connections == [True, False]
    assert client._marker_states["patient_marker"] is False
    client._on_tracking_status(status())
    assert connections == [True, False, True]


def test_individual_marker_expires_while_ndi_stays_online(client):
    with patch("bart_spine_ui.robot.ros_client.time.monotonic", return_value=100):
        client._on_tracking_status(status())
    with patch("bart_spine_ui.robot.ros_client.time.monotonic", return_value=102):
        client._on_tracking_status(status("tool_marker"))
        client._check_connection()
    assert client._tracking_connected is True
    assert client._marker_states["patient_marker"] is False
    assert client._marker_states["tool_marker"] is True


@pytest.mark.parametrize("visible,valid,age", [(True, False, 0.), (True, True, 2.), (True, True, float("nan"))])
def test_invalid_marker_not_ready(client, visible, valid, age):
    client._on_tracking_status(status(visible=visible, valid=valid, age=age))
    assert client._marker_states["patient_marker"] is False


def test_no_initial_heartbeat(client):
    with patch("bart_spine_ui.robot.ros_client.time.monotonic", return_value=client._tracking_started + 2):
        client._check_connection()
    assert client._tracking_connected is False
    assert not any(client._marker_states.values())
