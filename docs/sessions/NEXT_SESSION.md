# Next session — start here

## Where things stand

- Branch: phase3-fixes @ 6c71a82
- ArduCopter pinned: Copter-4.7.2 @ fb773567896014da007bca58358704d4a0d8516f (ardupilot.lock and metadata are committed)
- Unit tests on the laptop at that hash: 46 passed, 1 skipped
- Step list: DEADSTICK_STEPS.md. Part A is done (A1–A14). Part B is stuck at B7.
- Full pod archive (run logs, flight logs, built simulator): C:\Users\elxsh\Projects\deadstick-pod-archive\2026-11-06\

## Why B7 is stuck

- Last run: r01 → ERROR, "No HEARTBEAT from tcp:127.0.0.1:5760 within 90s" (evidence: docs/sessions/2026-11-06/runs/sitl_2c6fd1bc-eef).
- The simulator itself works: a manual test connecting once with pymavlink got three heartbeats in 1.9 s.
- The harness connects over TCP but receives nothing. SITL's TCP port serves one client at a time, so the harness can end up holding a connection the simulator never serves.
- "Exitting" in sitl.log is the harness shutting SITL down after its 90 s wait, not a crash.

## First task: A15 (laptop)

Switch the harness from TCP to UDP so there is no connection race:

1. Before starting SITL, the harness opens `mavutil.mavlink_connection("udpin:127.0.0.1:<port>")`, with port = 14550 + 10 × instance.
2. Start SITL with `--serial0 udpclient:127.0.0.1:<port>` so it sends MAVLink to the harness as soon as it boots. Confirm the exact option name in the pinned source (`libraries/AP_HAL_SITL/SITL_cmdline.cpp`, Copter-4.7.2) before relying on it.
3. Wait for HEARTBEAT on that connection (90 s total, never close and reopen during startup).
4. Reboot handling: after reboot, keep listening on the same UDP port; SITL resumes sending.
5. Record the MAVLink URL in provenance. Unit tests: the SITL command contains `--serial0 udpclient:`, and no `tcp:` URL is used anywhere in `deadstick/sim/`.

Commit "Use UDP from SITL to the harness instead of TCP", push from the laptop.

## Pod on resume

1. Start a pod with the same template as before if possible (built_on.txt records the OS).
2. Run `scripts/pod_b1_b5.sh` steps B1–B2 only (clone, venv, unit tests).
3. Restore the simulator instead of rebuilding: copy `sitl_build/arducopter` and `sitl_build/copter.parm` from the archive to the pod at `ardupilot/build/sitl/bin/arducopter` and `ardupilot/Tools/autotest/default_params/copter.parm`, then run `sha256sum` and compare with `SHA256SUMS`, run `chmod +x` on the binary, and run it with `--help` to confirm it starts. If it will not run on this pod's image, rebuild with B3 instead.
4. Then B7 with `--speedup 1`.
5. Never push from the pod.

## Known open items

- B7–B16 not done. No .BIN fixtures or live-verdict tests committed yet (by design).
- r03 (battery) not yet run live; the simulated battery may need setup for the low-voltage failsafe to trigger.
- Pause archive used a host script with LF line endings after an earlier CRLF upload failed; pod `pkill -f "deadstick"` can match the SSH command line—use narrow patterns or run from a file on the pod if re-running P1 manually.

## First prompt for the coding agent next time

Read docs/sessions/NEXT_SESSION.md and DEADSTICK_STEPS.md. Do task A15 only, on the laptop, then stop and report the commit hash and unit test output.
