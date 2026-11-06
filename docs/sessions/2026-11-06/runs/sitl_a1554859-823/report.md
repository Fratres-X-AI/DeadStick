# DeadStick report: `r03_battery_low_triggers_land`

When battery failsafe low action is set to land, a battery-low condition must lead to LAND (requirement).

## Verdicts

- **ERROR** — Harness error: [Errno 2] No such file or directory: '/root/DeadStick/arducopter/build/sitl/bin/arducopter'

## Provenance

```json
{
  "param_file": "tests/fixtures/params/default.param",
  "param_sha256": "2433d518b422d6708b233317777961a5d6295f7ac7ccbad1d48ae5c8631692bd",
  "rule_file": "rules/copter/r03_battery_low_triggers_land.yaml",
  "rule_sha256": "032df5dca23d5fc5e0781b267d9cf2982bef81046538249f1735b9f449ddce1e",
  "simulator_speedup": 1.0,
  "sitl_instance": 0,
  "mavlink": "tcp:127.0.0.1:5760",
  "not_applied": [],
  "rejected": [],
  "file_params_not_applied": [],
  "file_params_rejected": [],
  "file_params_sha256": "2433d518b422d6708b233317777961a5d6295f7ac7ccbad1d48ae5c8631692bd"
}
```

These results describe behavior observed in ArduPilot SITL under the stated conditions. They are not a guarantee of real-world behavior.
