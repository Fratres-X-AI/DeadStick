---
name: Bug report
about: Report something that does not match the documented behavior
title: ''
labels: ''
assignees: ''
---

## DeadStick commit

Paste the output of `git rev-parse HEAD`.

## ArduCopter tag

From `ardupilot.lock` (for example `Copter-4.7.2`) or state “not applicable” for a pure `deadstick run` issue.

## Rule file

Path under `rules/copter/…` (for example `rules/copter/r01_rc_loss_disarmed_blocks_arming.yaml`).

## Parameter file

Path or attach a minimal `.param` that shows the bug.

## What happened

Describe expected vs actual behavior.

## Verdict and output

Paste the **verdict** line from the console and attach or paste `result.json` from the run.
