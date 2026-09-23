#!/usr/bin/env bash
set -eo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export ROS_DOMAIN_ID=42
source /opt/ros/jazzy/setup.bash
source "${SCRIPT_DIR}/../spinerobot_ros2/install/setup.bash"
# Activate after ROS setup so the UI and its subprocesses use this environment.
source "${SCRIPT_DIR}/.venv/bin/activate"
exec "${SCRIPT_DIR}/.venv/bin/bart-spine-ui" "$@"
