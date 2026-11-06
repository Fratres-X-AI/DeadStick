# Known-bad parameter fixtures

Each line states the **expected** outcome when evaluated with the matching rule YAML
and the **unit-test** metadata shape (not pod-generated metadata).

| File | Rule | Expected |
|------|------|----------|
| `fs_thr_off.param` | `r02_rc_loss_rtl_when_configured` (requirement) | `FAIL` — radio failsafe disabled (`FS_THR_ENABLE = 0`). |
| `fs_thr_off.param` | `r01_rc_loss_disarmed_blocks_arming` (conformance) | `CANNOT_JUDGE` — precondition / feature off. |
| `batt_none.param` | `r03_battery_low_triggers_land` (requirement) | `FAIL` — low battery action disabled. |
| `fs_options_continue.param` | r01–r03 with default good params elsewhere | Same verdicts as the baseline good file for these rules (continue-in-Auto is out of scope until phase 6). |
| `rtl_alt_legacy.param` | r01–r03 | Unchanged verdicts; `RTL_ALT` should surface as **not applied** in harness reports when the firmware uses `RTL_ALT_M` instead. |
