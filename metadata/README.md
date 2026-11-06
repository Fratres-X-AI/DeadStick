# Generated ArduPilot parameter metadata

The file `Copter-4.7.2.json` in this directory is **generated** from ArduPilot source. It is **not** hand-written DeadStick code.

## How it is produced

1. Check out the ArduPilot tree at the **tag and commit** recorded in `ardupilot.lock` in the repository root.
2. Run ArduPilot’s `Tools/autotest/param_metadata/param_parse.py` (see `scripts/build_sitl.sh` for the exact invocation).
3. Normalize the raw JSON with `scripts/normalize_apm_pdef.py` into `metadata/<tag>.json`.

Regenerating after a new pin should use `scripts/build_sitl.sh` (full SITL build and metadata) or `scripts/generate_metadata.sh` when the firmware tree is already built.

## License

ArduPilot is licensed under **GPL-3.0**. See the [ArduPilot license](https://github.com/ArduPilot/ardupilot/blob/master/COPYING.txt).

The rest of this repository is **MIT** (see root `LICENSE`). Including generated GPL-sourced parameter descriptions alongside MIT-licensed tooling raises a **licensing question** (distribution of combined work). This README documents **provenance only**; it does not provide legal advice. If you redistribute or sell products built around this bench, ask a qualified lawyer whether to keep generated files in-repo or regenerate them at build time from a pinned ArduPilot checkout.

## Why it is here

The metadata file is checked in so runs are **reproducible**: the same parameter labels and bitmask text drive `CANNOT_JUDGE` and expect logic without depending on a live ArduPilot tree for ordinary development.
