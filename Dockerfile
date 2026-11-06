# CPU-only image for RunPod / Linux hosts. Build ArduPilot SITL with scripts/build_sitl.sh separately.
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace/DeadStick
COPY . /workspace/DeadStick

RUN pip3 install --break-system-packages --no-cache-dir -e ".[dev]"

ENV PATH="/usr/local/bin:$PATH"
CMD ["deadstick", "--help"]
