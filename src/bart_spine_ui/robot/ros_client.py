from __future__ import annotations

import time

import rclpy
from PySide6.QtCore import QObject, QTimer, Signal
from rclpy.node import Node
from sensor_msgs.msg import JointState
from spinerobot_interfaces.msg import TrackingStatus


class _RobotRosNode(Node):
    """Internal ROS 2 node used by the BART Spine UI."""

    def __init__(self, joint_state_callback, tracking_callback):
        super().__init__("bart_spine_ui")

        self._joint_state_sub = self.create_subscription(
            JointState,
            "/xarm/joint_states",
            joint_state_callback,
            10,
        )

        self._tracking_sub = self.create_subscription(
            TrackingStatus, "/tracking/status", tracking_callback, 10
        )


class RobotRosClient(QObject):
    """Qt-friendly ROS 2 interface for robot state."""

    joint_state_changed = Signal(object)
    connection_changed = Signal(bool)
    ros_error = Signal(str)
    tracking_connection_changed = Signal(bool)
    marker_changed = Signal(str, bool)

    MARKER_FRAMES = ("tool_marker", "robot_marker", "patient_marker")

    CONNECTION_TIMEOUT_S = 1.0

    def __init__(self, parent=None):
        super().__init__(parent)

        self._node = None
        self._last_message_time = 0.0
        self._connected = False
        self._owns_rclpy = False
        self._tracking_connected = None
        self._tracking_started = time.monotonic()
        self._last_tracking_time = None
        self._marker_times = {}
        self._marker_states = {}

        self._spin_timer = None
        self._watchdog_timer = None

        try:
            if not rclpy.ok():
                rclpy.init(args=None, domain_id=42)
                self._owns_rclpy = True

            if rclpy.get_default_context().get_domain_id() != 42:
                raise RuntimeError("BART Spine requires ROS domain 42")
            self._node = _RobotRosNode(
                self._on_joint_state, self._on_tracking_status
            )

            # Process ROS callbacks without blocking Qt.
            self._spin_timer = QTimer(self)
            self._spin_timer.timeout.connect(
                self._spin_once
            )
            self._spin_timer.start(10)

            # Check whether robot messages have stopped.
            self._watchdog_timer = QTimer(self)
            self._watchdog_timer.timeout.connect(
                self._check_connection
            )
            self._watchdog_timer.start(200)

        except Exception as exc:
            # Delay signal until Qt finishes constructing this object.
            QTimer.singleShot(
                0,
                lambda message=str(exc):
                    self.ros_error.emit(message),
            )

    def _spin_once(self):
        if self._node is None:
            return

        if not rclpy.ok():
            return

        try:
            rclpy.spin_once(
                self._node,
                timeout_sec=0.0,
            )

        except Exception as exc:
            self.ros_error.emit(str(exc))

    def _on_joint_state(self, msg: JointState):
        self._last_message_time = time.monotonic()

        if not self._connected:
            self._connected = True
            self.connection_changed.emit(True)

        state = {
            "names": list(msg.name),
            "positions": list(msg.position),
            "velocities": list(msg.velocity),
            "efforts": list(msg.effort),
        }

        self.joint_state_changed.emit(state)

    def _set_marker(self, frame: str, tracked: bool):
        if self._marker_states.get(frame) != tracked:
            self._marker_states[frame] = tracked
            self.marker_changed.emit(frame, tracked)

    def _on_tracking_status(self, msg: TrackingStatus):
        if msg.frame_id not in self.MARKER_FRAMES:
            return
        now = time.monotonic()
        self._last_tracking_time = now
        self._marker_times[msg.frame_id] = now
        if self._tracking_connected is not True:
            self._tracking_connected = True
            self.tracking_connection_changed.emit(True)
        self._set_marker(
            msg.frame_id,
            bool(msg.visible and msg.valid and 0 <= msg.age_sec <= self.CONNECTION_TIMEOUT_S),
        )

    def _check_connection(self):
        now = time.monotonic()
        if self._connected and now - self._last_message_time > self.CONNECTION_TIMEOUT_S:
            self._connected = False
            self.connection_changed.emit(False)

        last_tracking = self._last_tracking_time
        if last_tracking is None:
            last_tracking = self._tracking_started
        if now - last_tracking > self.CONNECTION_TIMEOUT_S:
            if self._tracking_connected is not False:
                self._tracking_connected = False
                self.tracking_connection_changed.emit(False)
        for frame in self.MARKER_FRAMES:
            if now - self._marker_times.get(frame, self._tracking_started) > self.CONNECTION_TIMEOUT_S:
                self._set_marker(frame, False)

    def shutdown(self):
        if self._spin_timer is not None:
            self._spin_timer.stop()

        if self._watchdog_timer is not None:
            self._watchdog_timer.stop()

        if self._node is not None:
            self._node.destroy_node()
            self._node = None

        if self._owns_rclpy and rclpy.ok():
            rclpy.shutdown()
