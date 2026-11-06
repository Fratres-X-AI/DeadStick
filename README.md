# DeadStick — what your drone does when something dies

DeadStick runs **scripted faults** against **ArduPilot SITL**, records a **flight log**, and **judges** the result against **YAML rules** and your **parameter file**. Simulated, logged, judged — never “proven safe.”

[![CI](https://github.com/Fratres-X-AI/DeadStick/actions/workflows/ci.yml/badge.svg)](https://github.com/Fratres-X-AI/DeadStick/actions/workflows/ci.yml)

## Status

**Early development.** The evaluation engine and unit tests work. **Live SITL runs** through `deadstick sitl-run` are still being brought up. **Not ready** for operational use.

## What it does

1. You write or pick a **rule** (YAML): what should happen under a fault (radio loss, battery low, etc.).
2. You supply a **parameter file** (`.param`) and **firmware metadata** (JSON derived from the pinned ArduCopter tree — see `ardupilot.lock`).
3. The **harness** drives SITL, injects the fault, and produces a **flight log** (`.BIN` preferred).
4. `deadstick run` (or the harness) evaluates the log on the **timeline** built from that record. The **verdict** is from the **log**, not from a live telemetry guess.

Design details: [docs/DESIGN.md](docs/DESIGN.md).

## Verdicts

| Verdict | When |
|--------|------|
| **PASS** | Every check passed for that rule on the supplied log and parameters. |
| **FAIL** | A check failed after the fault was confirmed (when confirmation is required). |
| **CANNOT_JUDGE** | Missing parameters, precondition false, ambiguous metadata, unknown fault time, or fault not confirmed — no behavioral FAIL. |
| **ERROR** | Bad inputs, harness failure, or evaluator error — not a verdict on the vehicle. |

## Quick start

```bash
git clone https://github.com/Fratres-X-AI/DeadStick.git
cd DeadStick
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
deadstick explain rules/copter/r01_rc_loss_disarmed_blocks_arming.yaml
python -m pytest tests/unit -q
```

For offline evaluation you need a rule, params, metadata JSON under `metadata/`, and a timeline (`.jsonl` or `.BIN`). See `deadstick run --help`.

## Running live simulations

Use a **Linux x86-64** machine (physical or virtual) with enough CPU and disk to build ArduCopter SITL.

1. Clone this repository and the `ardupilot` submodule or tree expected by `scripts/build_sitl.sh`.
2. Run **`scripts/build_sitl.sh`** to build the **pinned** ArduCopter Copter SITL. The build **takes a long time** and uses **many CPU cores**; no GPU is required for SITL.
3. Run **`deadstick sitl-run --help`** for arguments (rule path, params, metadata, path to `arducopter` binary, results directory).

## How to read a `FAIL`

A **`FAIL`** means the fault was **injected**, **confirmed** in the log (for example STATUSTEXT within `confirm_fault.within_s` after the inject time), and an **expectation check** then found forbidden or missing behavior (wrong mode, altitude, arming when it should be refused, etc.).

Example (abbreviated):

- **Rule**: requirement — on RC loss, enter the configured failsafe mode within the time bound.
- **Parameter meaning**: from metadata + your `.param` values (for example RTL vs Land from `FS_THR_ENABLE`).
- **Timeline**: `fault_injected` at *t*, confirmation text at *t + 200ms*, no expected mode change before *t + limit* → **FAIL**, with evidence on the timeline attached to the result.

## Starter rules

| Rule | One-line |
|------|----------|
| **r01** | Radio failsafe enabled and RC-loss while disarmed → arming must be refused (conformance). |
| **r02** | RC loss with RTL configured → vehicle must enter RTL within the bound (requirement). |
| **r03** | Battery low action set to land → battery-low inject must lead to LAND (requirement). |

Files: `rules/copter/r01_*.yaml`, `r02_*.yaml`, `r03_*.yaml`.

## Safety notice

Results describe behavior **observed in ArduPilot SITL** under the stated parameters, rules, and logs. They are **not** a guarantee of real-world behavior, **not** certification, and **not** a substitute for flight testing. The bench only talks to a **local simulator**; there is **no** code path to arm a real aircraft from this tool.

## Contributing

Bug reports and pull requests are welcome. Please run `python -m pytest tests/unit -q` before submitting. A change must never weaken a check just to make a run pass.

## License

MIT — see [LICENSE](LICENSE).

## Acknowledgements

- [ArduPilot](https://ardupilot.org/) — autopilot firmware and SITL.
- [pymavlink](https://github.com/ArduPilot/pymavlink) — MAVLink parsing and helpers.

### Third-party generated data

Firmware parameter metadata under `metadata/` is generated from ArduPilot sources. See [metadata/README.md](metadata/README.md) for origin and license notes.
