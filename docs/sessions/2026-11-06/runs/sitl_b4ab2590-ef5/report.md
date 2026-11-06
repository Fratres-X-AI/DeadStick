# DeadStick report: `r01_rc_loss_disarmed_blocks_arming`

With radio failsafe enabled, an RC-loss fault while disarmed must block arming (conformance with expected prearm gating).

## Verdicts

- **ERROR** — Harness error: No HEARTBEAT

## Provenance

```json
{
  "param_file": "tests/fixtures/params/default.param",
  "param_sha256": "2433d518b422d6708b233317777961a5d6295f7ac7ccbad1d48ae5c8631692bd",
  "rule_file": "rules/copter/r01_rc_loss_disarmed_blocks_arming.yaml",
  "rule_sha256": "fd44bc2d1551fbf280e42bd55994eefb98cfe8e47ef4098fe7a0358e2f779570",
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
