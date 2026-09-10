#!/usr/bin/env bash
set -euo pipefail

mkdir -p "${XDG_RUNTIME_DIR}" "${TOTALSEG_HOME_DIR}"
chmod 0700 "${XDG_RUNTIME_DIR}"

exec "$@"
