#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 /path/to/ct-or-dicom-directory" >&2
    exit 2
fi

for command_name in docker xauth; do
    if ! command -v "${command_name}" >/dev/null 2>&1; then
        echo "Required command not found: ${command_name}" >&2
        exit 1
    fi
done

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is required (the 'docker compose' command)." >&2
    exit 1
fi

if [[ -z "${DISPLAY:-}" ]]; then
    echo "DISPLAY is not set. Run this script from the Ubuntu graphical session." >&2
    exit 1
fi

ct_data_dir="$(realpath -- "$1")"
if [[ ! -d "${ct_data_dir}" ]]; then
    echo "CT/DICOM directory does not exist: ${ct_data_dir}" >&2
    exit 1
fi
if [[ ! -w "${ct_data_dir}" ]]; then
    echo "CT/DICOM directory must be writable for segmentation output: ${ct_data_dir}" >&2
    exit 1
fi

totalseg_cache_dir="${TOTALSEG_CACHE_DIR:-${HOME}/.cache/bart-spine-ui}"
mkdir -p "${totalseg_cache_dir}"
totalseg_cache_dir="$(realpath -- "${totalseg_cache_dir}")"

xauth_file="$(mktemp --tmpdir bart-spine-xauth.XXXXXX)"
trap 'rm -f -- "${xauth_file}"' EXIT

# FamilyWild makes the current display cookie match the container hostname
# without opening the X server to every local Docker container.
xauth nlist "${DISPLAY}" | sed -e 's/^..../ffff/' | xauth -f "${xauth_file}" nmerge -
if [[ ! -s "${xauth_file}" ]]; then
    echo "Could not obtain an X11 authorization cookie for DISPLAY=${DISPLAY}." >&2
    echo "Log in through the Ubuntu graphical session and try again." >&2
    exit 1
fi

export CT_DATA_DIR="${ct_data_dir}"
export HOST_GID="$(id -g)"
export HOST_UID="$(id -u)"
export TOTALSEG_CACHE_DIR="${totalseg_cache_dir}"
export XAUTH_FILE="${xauth_file}"

docker compose --project-directory "${script_dir}" \
    -f "${script_dir}/compose.yaml" run --build --rm bart-spine-ui
