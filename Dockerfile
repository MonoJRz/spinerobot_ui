ARG TOTALSEGMENTATOR_IMAGE=wasserth/totalsegmentator:2.11.0
FROM ${TOTALSEGMENTATOR_IMAGE}

USER root

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Runtime libraries required by PySide6's XCB platform plugin and VTK OpenGL.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libdbus-1-3 \
        libegl1 \
        libfontconfig1 \
        libgl1 \
        libglib2.0-0 \
        libice6 \
        libsm6 \
        libx11-6 \
        libx11-xcb1 \
        libxext6 \
        libxrender1 \
        libxcb-cursor0 \
        libxcb-icccm4 \
        libxcb-image0 \
        libxcb-keysyms1 \
        libxcb-randr0 \
        libxcb-render-util0 \
        libxcb-shape0 \
        libxcb-xfixes0 \
        libxcb-xinerama0 \
        libxkbcommon-x11-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/bart-spine-ui

COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m pip install --no-cache-dir . \
    && command -v TotalSegmentator \
    && command -v bart-spine-ui

COPY docker/entrypoint.sh /usr/local/bin/bart-spine-entrypoint
RUN chmod 0755 /usr/local/bin/bart-spine-entrypoint

ENV BART_DATA_DIR=/data \
    BART_TOTALSEG_DEVICE=gpu \
    HOME=/cache \
    TOTALSEG_HOME_DIR=/cache/totalsegmentator \
    XDG_RUNTIME_DIR=/tmp/bart-runtime

ENTRYPOINT ["/usr/local/bin/bart-spine-entrypoint"]
CMD ["bart-spine-ui"]
