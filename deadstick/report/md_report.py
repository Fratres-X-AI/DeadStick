from __future__ import annotations

from pathlib import Path

from deadstick.verdict import Result


def write_report_md(
    path: Path,
    *,
    rule_id: str,
    rule_say: str,
    results: list[Result],
    provenance: dict[str, str | float | int | None],
) -> None:
    lines = [
        f"# DeadStick report: `{rule_id}`",
        "",
        rule_say.strip(),
        "",
        "## Verdicts",
        "",
    ]
    for r in results:
        lines.append(f"- **{r.verdict.value}** — {r.reason}")
        if r.evidence:
            lines.append(f"  - evidence: `{r.evidence}`")
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            "```json",
            __import__("json").dumps(provenance, indent=2),
            "```",
            "",
            "These results describe behavior observed in ArduPilot SITL under the stated conditions. "
            "They are not a guarantee of real-world behavior.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")
