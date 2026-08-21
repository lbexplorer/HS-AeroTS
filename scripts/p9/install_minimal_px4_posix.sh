#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: wsl -d Ubuntu-20.04 -u root -- bash /mnt/d/UAV/scripts/p9/install_minimal_px4_posix.sh" >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  build-essential ca-certificates ccache cmake git make ninja-build pkg-config rsync \
  unzip wget xsltproc libxml2-utils python3 python3-dev python3-pip python3-setuptools \
  python3-wheel python3-empy python3-jinja2 python3-numpy python3-serial python3-yaml

python3 -m pip install --no-cache-dir 'empy==3.3.4' 'pyulog==1.2.4' 'toml>=0.9,<1' packaging

echo "Minimal PX4 POSIX toolchain installed. Gazebo, ROS, QGroundControl and NuttX were not installed."

