# DeadStick report: `r02_rc_loss_rtl_when_configured`

When RC loss action is configured for RTL via FS_THR_ENABLE, the vehicle must enter RTL within a bounded time after fault injection (requirement).

## Verdicts

- **ERROR** — Harness error: [Errno 2] No such file or directory: '/root/DeadStick/arducopter/build/sitl/bin/arducopter'

## Provenance

```json
{
  "param_file": "tests/fixtures/params/bad/fs_thr_off.param",
  "param_sha256": "bcf9210cfa9e20438b8dbcae92559deaf5c9bb173cabf591a45389631471f51b",
  "rule_file": "rules/copter/r02_rc_loss_rtl_when_configured.yaml",
  "rule_sha256": "89b96e322122db5562aa0309d16b0ce002c3338485a7aa955fbe9c12c1874930",
  "simulator_speedup": 1.0,
  "sitl_instance": 0,
  "mavlink": "tcp:127.0.0.1:5760",
  "not_applied": [],
  "rejected": [],
  "file_params_not_applied": [],
  "file_params_rejected": [],
  "file_params_sha256": "bcf9210cfa9e20438b8dbcae92559deaf5c9bb173cabf591a45389631471f51b"
}
```

These results describe behavior observed in ArduPilot SITL under the stated conditions. They are not a guarantee of real-world behavior.
