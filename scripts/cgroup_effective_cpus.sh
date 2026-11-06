#!/usr/bin/env bash
# Print integer CPU quota for this cgroup (v2 cpu.max or v1 cfs quota), else nproc.
# RunPod/cgroups may report fewer CPUs than the host's nproc — use this for -j / workers.
set -euo pipefail

ceiling_div() {
  local a=$1 b=$2
  if [ "$b" -le 0 ]; then echo 1; return; fi
  echo $(( (a + b - 1) / b ))
}

# cgroup v2
if [ -r /sys/fs/cgroup/cpu.max ]; then
  read -r q p < /sys/fs/cgroup/cpu.max
  if [ "$q" = "max" ]; then
    nproc
    exit 0
  fi
  if [ -n "$p" ] && [ "$p" -gt 0 ] 2>/dev/null; then
    cpus=$(ceiling_div "$q" "$p")
    if [ "$cpus" -lt 1 ]; then cpus=1; fi
    echo "$cpus"
    exit 0
  fi
fi

# cgroup v1
if [ -r /sys/fs/cgroup/cpu/cpu.cfs_quota_us ] && [ -r /sys/fs/cgroup/cpu/cpu.cfs_period_us ]; then
  q=$(cat /sys/fs/cgroup/cpu/cpu.cfs_quota_us)
  p=$(cat /sys/fs/cgroup/cpu/cpu.cfs_period_us)
  if [ "$q" = "-1" ] || [ -z "$p" ] || [ "$p" -eq 0 ]; then
    nproc
    exit 0
  fi
  cpus=$(ceiling_div "$q" "$p")
  if [ "$cpus" -lt 1 ]; then cpus=1; fi
  echo "$cpus"
  exit 0
fi

nproc
