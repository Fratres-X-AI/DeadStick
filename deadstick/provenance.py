from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_provenance(
    *,
    firmware_tag: str | None = None,
    firmware_commit: str | None = None,
    param_path: Path | None = None,
    rule_path: Path | None = None,
    rule_text: str | None = None,
    simulator_speedup: float | None = None,
    random_seed: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if firmware_tag:
        out["firmware_git_tag"] = firmware_tag
    if firmware_commit:
        out["firmware_commit"] = firmware_commit
    if param_path is not None:
        out["param_file"] = str(param_path)
        out["param_sha256"] = sha256_file(param_path)
    if rule_path is not None:
        out["rule_file"] = str(rule_path)
        out["rule_sha256"] = sha256_file(rule_path)
    elif rule_text is not None:
        out["rule_sha256"] = sha256_text(rule_text)
    if simulator_speedup is not None:
        out["simulator_speedup"] = simulator_speedup
    if random_seed is not None:
        out["random_seed"] = random_seed
    if extra:
        out.update(extra)
    return out


def provenance_to_json(prov: dict[str, Any]) -> str:
    return json.dumps(prov, indent=2, sort_keys=True)
