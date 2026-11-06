# Contributing

## Setup

```bash
git clone https://github.com/Fratres-X-AI/DeadStick.git
cd DeadStick
python3 -m venv .venv
./.venv/bin/pip install -e ".[dev]"
```

## Tests

```bash
python -m pytest tests/unit -q
```

Pull requests should keep this suite green.

## Lint and types

```bash
ruff check .
ruff format --check .
mypy deadstick
```

Optional: install [pre-commit](https://pre-commit.com/) and run `pre-commit install` to use `.pre-commit-config.yaml` (Ruff) before you commit.

## Issues and pull requests

Use GitHub issues for bugs and feature ideas. Pull requests should be small and focused.

## Rule for checks

A change must **never** weaken an expectation or a precondition just to make a run pass. If a rule is wrong, change the rule text and the tests together, with a clear reason in the pull request description.
