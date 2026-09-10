from __future__ import annotations

import time

import rclpy
from PySide6.QtCore import QObject, QTimer, Signal
from rclpy.node import Node
from sensor_msgs.msg import JointState


class _RobotRosNode(Node):
    """Internal ROS 2 node used by the BART Spine UI."""

    def __init__(self, joint_state_callback):
        super().__init__("bart_spine_ui")

        self._joint_state_sub = self.create_subscription(
            JointState,
            "/xarm/joint_states",
            joint_state_callback,
            10,
        )


class RobotRosClient(QObject):
    """Qt-friendly ROS 2 interface for robot state."""

    joint_state_changed = Signal(object)
    connection_changed = Signal(bool)
    ros_error = Signal(str)

    CONNECTION_TIMEOUT_S = 1.0

    def __init__(self, parent=None):
        super().__init__(parent)

        self._node = None
        self._last_message_time = 0.0
        self._connected = False
        self._owns_rclpy = False

        self._spin_timer = None
        self._watchdog_timer = None

        try:
            if not rclpy.ok():
                rclpy.init(args=None)
                self._owns_rclpy = True

            self._node = _RobotRosNode(
                self._on_joint_state
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

    def _check_connection(self):
        if not self._connected:
            return

        age = (
            time.monotonic()
            - self._last_message_time
        )

        if age > self.CONNECTION_TIMEOUT_S:
            self._connected = False
            self.connection_changed.emit(False)

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