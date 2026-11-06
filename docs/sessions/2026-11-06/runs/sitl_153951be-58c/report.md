# DeadStick report: `r01_rc_loss_disarmed_blocks_arming`

With radio failsafe enabled, an RC-loss fault while disarmed must block arming (conformance with expected prearm gating).

## Verdicts

- **ERROR** — Harness error: [Errno 2] No such file or directory: '/root/DeadStick/arducopter/build/sitl/bin/arducopter'

## Provenance

```json
{
  "param_file": "tests/fixtures/params/default.param",
  "param_sha256": "2433d518b422d6708b233317777961a5d6295f7ac7ccbad1d48ae5c8631692bd",
  "rule_file": "rules/copter/r01_rc_loss_disarmed_blocks_arming.yaml",
  "rule_sha256": "c950e9b09e323b3e864bc8f70f31c55002b6991d0fcde6c1fb21a118817b0e3c",
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
