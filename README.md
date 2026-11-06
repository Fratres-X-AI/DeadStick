# DeadStick (autopilot safety bench)

[![CI](https://github.com/Fratres-X-AI/DeadStick/actions/workflows/ci.yml/badge.svg)](https://github.com/Fratres-X-AI/DeadStick/actions/workflows/ci.yml)

Python CLI: **rule YAML** + **`.param`** + **firmware metadata** + **log** → `PASS` / `FAIL` / `CANNOT_JUDGE` / `ERROR`.

- **`ERROR`**: harness or missing signal — not a verdict on the autopilot.
- Results describe behavior **observed in simulation** under stated conditions — never “proven safe,” “certified,” or “guaranteed.”

Upstream: [Fratres-X-AI/DeadStick](https://github.com/Fratres-X-AI/DeadStick)

Also installed as `apbench` for compatibility with the build plan name.

## Install (dev)

```bash
git clone https://github.com/Fratres-X-AI/DeadStick.git
cd DeadStick
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
deadstick --help
```

## Commands

| Command | Purpose |
|--------|---------|
| `deadstick explain rules/copter/r01_….yaml` | Rule summary; **no** simulator. |
| `deadstick run -r RULE -p PARAMS -m METADATA -l TIMELINE.jsonl [--dataflash X.BIN]` | Evaluate; refuses `FAKE_*` metadata / `"fake": true`. Verdict from **`.BIN`** when `--dataflash` is set (vehicle record). |
| `deadstick run-all --rules-dir rules/copter -p … -m … -l …` | All rules in folder, sequential. |
| `deadstick sitl-run …` | Live SITL on Linux/RunPod (see `--help`); writes `results/sitl_<id>/`. |
| `deadstick report results/.../result.json` | Short summary. |

## Pre–phase-3 correctness (SITL / dataflash)

- **MAVLink to SITL** uses `tcp:` (bare `host:port` in pymavlink is UDP). Default in `deadstick.sim.link.connect` is `tcp:127.0.0.1:5760`.
- **`.BIN` time base** uses `TimeUS / 1000` as milliseconds since boot (not pymavlink’s wall-clock `_timestamp`).
- **MODE** rows from dataflash map numeric mode via `mavutil.mode_mapping_acm`; unknown numbers → `UNKNOWN_n` and mode checks return **CANNOT_JUDGE**, not false FAIL.
- **Fault time for `.BIN`** comes from `PARM` lines (`SIM_RC_FAIL`, `SIM_BATT_VOLTAGE` below `BATT_LOW_VOLT`) as synthetic `fault_injected` events; pass the same `.param` values into `deadstick run` so thresholds match.
- **Rules** no longer use `anchor_ms`; expectation windows anchor on `fault_injected` (or schema error if `anchor_ms` appears).
- **`LOG_DISARMED`** is applied before reboot in `sitl-run` so disarmed rules still get logs.
- **`scripts/pod_pulse.sh`**: optional pod heartbeat loop (e.g. `bash scripts/pod_pulse.sh 20 120` for 20 check-ins, 120s apart).

## How to read a `FAIL`

A **`FAIL`** means: the fault was injected and **confirmed** by the vehicle (STATUSTEXT / ERR in the log within `confirm_fault.within_s`), then an expectation check saw forbidden or missing behavior.

Example (abbreviated):

- **Rule**: requirement — on RC loss, enter configured failsafe mode within the time bound.
- **Parameter**: `FS_THR_ENABLE` meaning RTL from metadata + params file.
- **Timeline**: `fault_injected` at *t*, confirmation “radio failsafe” at *t+200ms*, no `RTL` mode before *t + limit* → **FAIL**, with the mode trace in `evidence`.

## Fake metadata guard

`tests/fixtures/metadata/FAKE_copter_min.json` is **unit-test only** (`"fake": true`). The CLI refuses it for real runs; use metadata from `metadata/` or the pod build.

Pod-generated metadata belongs in `metadata/Copter-<tag>.json` (see plan phase 2).

## Layout

- `deadstick/` — package (evaluate, timeline, rules, sim harness, reports).
- `rules/copter/` — YAML rules.
- `scripts/build_sitl.sh` — **[HEAVY]** ArduPilot SITL on RunPod CPU only.
- `scripts/matrix_run.py` — matrix skeleton (phase 5).
- `.github/workflows/ci.yml` — `pytest` on push/PR.

## RunPod notes

See [AUTOPILOT_SAFETY_BENCH_PLAN.md](AUTOPILOT_SAFETY_BENCH_PLAN.md).

- **Pod class:** this stack is **CPU/RAM**-bound (SITL build + Python). Use whatever RunPod tier has enough cores and disk for `./waf copter`. If the only available template is GPU-class but you need the **CPU** count (e.g. 32 vCPU), that’s fine — you don’t need to use the GPU. Prefer a cheaper CPU-oriented template **when RunPod offers one** so you’re not paying for idle silicon; there isn’t always one. **Do not install CUDA** unless you add a GPU workload later.
- **Shell on Windows:** drive SSH/SCP from **Git Bash** (or WSL bash), not PowerShell — PowerShell mangles `ssh` quoting, `$()`, and heredocs.
- **Parallelism:** `scripts/build_sitl.sh` and `scripts/matrix_run.py` derive worker / `waf -j` counts from **cgroup CPU quota** first (`scripts/cgroup_effective_cpus.sh` and `scripts/effective_cpus.py`), then fall back to `nproc` / `os.cpu_count()`.
- Ubuntu images may need a venv under `/root` and `PYTEST_ADDOPTS='-o cache_dir=/tmp/...'` if `/workspace` disallows `.pytest_cache`.
