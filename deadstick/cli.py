from __future__ import annotations

import uuid
from dataclasses import replace
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from deadstick.evaluate.runner import evaluate_rule
from deadstick.metadata import load_metadata
from deadstick.param_file import load_param_file
from deadstick.provenance import build_provenance
from deadstick.report.json_report import write_result_json
from deadstick.report.md_report import write_report_md
from deadstick.rules.loader import load_rule
from deadstick.timeline.dataflash import bin_to_timeline
from deadstick.timeline.jsonl import load_jsonl
from deadstick.verdict import Result, Verdict

app = typer.Typer(help="DeadStick — autopilot safety bench (SITL-first).")
console = Console()


def _aggregate_worst(rows: list[Result]) -> Verdict:
    order = [Verdict.PASS, Verdict.CANNOT_JUDGE, Verdict.FAIL, Verdict.ERROR]
    worst = Verdict.PASS
    for res in rows:
        if order.index(res.verdict) > order.index(worst):
            worst = res.verdict
    return worst


@app.command("explain")
def explain(rule: Path) -> None:
    """Print a human-readable summary of a rule YAML (no simulator)."""
    rf = load_rule(rule)
    console.print(f"[bold]{rf.id}[/bold] — {rf.say}")
    console.print(f"kind: {rf.kind.value}  vehicle: {rf.vehicle}")
    if rf.requires_params:
        console.print("requires_params: " + ", ".join(rf.requires_params))
    if rf.precondition:
        console.print(f"precondition: {rf.precondition.expr!r}")
        console.print(f"  if not: {rf.precondition.reason_if_not}")
    if rf.confirm_fault:
        console.print(f"confirm_fault: within_s={rf.confirm_fault.within_s}")
        for b in rf.confirm_fault.any_of:
            console.print(f"  - {b.model_dump(exclude_none=True)}")
    console.print("scenario:")
    for step in rf.scenario:
        console.print(f"  - {step.step}: {step.args}")
    if rf.expect:
        console.print("expect:")
        for e in rf.expect:
            console.print(f"  - {e.check}: {e.payload}")


@app.command("run")
def run_cmd(
    rule: Path = typer.Option(..., "--rule", "-r", help="Rule YAML path"),
    params: Path = typer.Option(..., "--params", "-p", help=".param file"),
    metadata: Path = typer.Option(..., "--metadata", "-m", help="Firmware metadata JSON"),
    log: Path = typer.Option(..., "--log", "-l", help="Timeline .jsonl and/or dataflash .bin"),
    dataflash: Optional[Path] = typer.Option(
        None,
        "--dataflash",
        "-b",
        help="Optional dataflash .BIN (verdict uses this timeline when set; plan §0).",
    ),
    out_dir: Optional[Path] = typer.Option(
        None,
        "--out-dir",
        "-o",
        help="results/<run_id> output (default: auto)",
    ),
    allow_fake: bool = typer.Option(
        False,
        "--allow-fake-metadata",
        help="Only for tests: allow FAKE_ / fake metadata (no real verdicts).",
    ),
    speedup: float = typer.Option(1.0, "--speedup", help="Record simulator speedup for provenance."),
    seed: Optional[int] = typer.Option(None, "--seed", help="Random seed for provenance."),
) -> None:
    """
    Evaluate one rule. If --dataflash is set, the verdict is computed from the .BIN
    timeline (vehicle record); otherwise from the JSONL timeline.
    """
    from deadstick.metadata import assert_not_fake_metadata

    run_id = str(uuid.uuid4())[:8]
    base = out_dir or (Path("results") / f"run_{run_id}")
    base.mkdir(parents=True, exist_ok=True)

    rf = load_rule(rule)
    param_map = load_param_file(params)
    meta = load_metadata(metadata)
    if not allow_fake:
        try:
            assert_not_fake_metadata(metadata, meta)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=2) from exc

    timeline_jsonl = load_jsonl(log) if log.suffix.lower() == ".jsonl" else None
    if dataflash is not None:
        timeline = bin_to_timeline(dataflash)
        primary_log = dataflash
    elif timeline_jsonl is not None:
        timeline = timeline_jsonl
        primary_log = log
    else:
        timeline = bin_to_timeline(log)
        primary_log = log

    prov = build_provenance(
        param_path=params,
        rule_path=rule,
        simulator_speedup=speedup,
        random_seed=seed,
        extra={"run_id": run_id, "rule_id": rf.id},
    )
    raw = evaluate_rule(rule=rf, params=param_map, metadata=meta, timeline=timeline)
    rows = [replace(r, provenance={**r.provenance, **prov}) for r in raw]

    table = Table(title=f"Results for {rf.id}")
    table.add_column("verdict")
    table.add_column("reason")
    for res in rows:
        color = {
            Verdict.PASS: "green",
            Verdict.FAIL: "red",
            Verdict.CANNOT_JUDGE: "yellow",
            Verdict.ERROR: "magenta",
        }.get(res.verdict, "white")
        table.add_row(f"[{color}]{res.verdict.value}[/{color}]", res.reason)
    console.print(table)

    write_result_json(
        base / "result.json",
        rule_id=rf.id,
        results=rows,
        provenance=prov,
        timeline_path=log if timeline_jsonl is not None else None,
        dataflash_path=dataflash,
    )
    write_report_md(
        base / "report.md",
        rule_id=rf.id,
        rule_say=rf.say,
        results=rows,
        provenance={k: v for k, v in prov.items()},
    )
    console.print(f"[dim]Wrote {base / 'result.json'} and report.md[/dim]")

    worst = _aggregate_worst(rows)
    if worst in (Verdict.FAIL, Verdict.ERROR):
        raise typer.Exit(code=1)


@app.command("run-all")
def run_all(
    rules_dir: Path = typer.Option(Path("rules/copter"), "--rules-dir"),
    params: Path = typer.Option(..., "--params", "-p"),
    metadata: Path = typer.Option(..., "--metadata", "-m"),
    log: Path = typer.Option(..., "--log", "-l"),
    dataflash: Optional[Path] = typer.Option(None, "--dataflash", "-b"),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", "-o"),
    allow_fake: bool = typer.Option(False, "--allow-fake-metadata"),
) -> None:
    """Run every rule YAML in a directory sequentially (one verdict set per rule)."""
    run_id = str(uuid.uuid4())[:8]
    base = out_dir or (Path("results") / f"batch_{run_id}")
    base.mkdir(parents=True, exist_ok=True)
    worst_overall = Verdict.PASS
    order = [Verdict.PASS, Verdict.CANNOT_JUDGE, Verdict.FAIL, Verdict.ERROR]
    for rule_path in sorted(rules_dir.glob("*.yaml")):
        rf = load_rule(rule_path)
        param_map = load_param_file(params)
        meta = load_metadata(metadata)
        if not allow_fake:
            from deadstick.metadata import assert_not_fake_metadata

            assert_not_fake_metadata(metadata, meta)
        if dataflash is not None:
            timeline = bin_to_timeline(dataflash)
        elif log.suffix.lower() == ".jsonl":
            timeline = load_jsonl(log)
        else:
            timeline = bin_to_timeline(log)
        prov = build_provenance(param_path=params, rule_path=rule_path, extra={"batch": run_id})
        rows = evaluate_rule(rule=rf, params=param_map, metadata=meta, timeline=timeline)
        w = _aggregate_worst(rows)
        if order.index(w) > order.index(worst_overall):
            worst_overall = w
        write_result_json(base / f"{rf.id}_result.json", rule_id=rf.id, results=rows, provenance=prov)
        write_report_md(
            base / f"{rf.id}_report.md",
            rule_id=rf.id,
            rule_say=rf.say,
            results=rows,
            provenance=dict(prov),
        )
    console.print(f"[bold]Batch worst verdict:[/bold] {worst_overall.value}")
    if worst_overall in (Verdict.FAIL, Verdict.ERROR):
        raise typer.Exit(code=1)


@app.command("report")
def report_cmd(result_json: Path) -> None:
    """Print a short summary from a result.json written by `deadstick run`."""
    import json

    data = json.loads(result_json.read_text(encoding="utf-8"))
    console.print(f"Rule: {data.get('rule_id')}")
    for r in data.get("results", []):
        console.print(f"  {r.get('verdict')}: {r.get('reason')}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
