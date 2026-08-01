# AGENTS.md

Instructions for AI coding agents (Claude Code and similar) working in this repository.

## Project state: in progress

This repo is being reworked from a thin `invenio-cli` extension into a standalone
Python CLI (`oarepo-cli`) that replaces three bash scripts (`library_runner.sh`,
`repository_runner.sh`, `repository_installer.sh`). **The target architecture is
fully designed in [`docs/architecture/`](./docs/architecture/) but mostly not yet
implemented.**

Do not assume any module named in the architecture docs (`core/context.py`,
`services/process.py`, `adapters/subprocess_executor.py`, etc.) already exists — check first. When implementing a piece of the design, follow
[`docs/architecture/implementation-steps.md`](./docs/architecture/implementation-steps.md)
phase by phase; don't jump ahead to later phases' modules before their
dependencies (earlier phases) exist.

Before starting implementation of a new step, create a new branch from `cli-as-python` branch (note: you might be on a different branch / not up-to-date, so you need to switch and pull first) and implement the step there.

After implementing a step, create a PR with the changes and request a review. The target branch of the PR will be `cli-as-python`.


## Where to look

| Need | Read |
|------|------|
| Orientation / executive summary of the whole design | [docs/architecture/README.md](./docs/architecture/README.md) |
| Feature inventory: every command/flag/env var the CLI must support, external tool deps, known issues in the old bash scripts | [docs/architecture/00-main-architecture.md](./docs/architecture/00-main-architecture.md) §1 |
| Design principles, ADRs (why Typer, why single executable, why no self-update, why no `shell=True`, why no parent-env mutation) | [00-main-architecture.md](./docs/architecture/00-main-architecture.md) §2, §8 |
| Target package layout, component diagrams, protocol interfaces (`ProcessExecutor`, `VirtualEnvironmentManager`, `PyProjectReader`), CLI command code samples | [docs/architecture/01-detailed-design.md](./docs/architecture/01-detailed-design.md) |
| How to test what you write (unit/contract/workflow/integration/characterization layers, fakes, fixtures) | [docs/architecture/02-testing-strategy.md](./docs/architecture/02-testing-strategy.md) |
| Shell-to-Python command mapping, breaking changes, env var semantics that must be preserved | [docs/architecture/03-migration-guide.md](./docs/architecture/03-migration-guide.md) |
| **The actual step-by-step build plan** — work through this in order | [docs/architecture/implementation-steps.md](./docs/architecture/implementation-steps.md) |

If two docs seem to disagree, `implementation-steps.md` and `01-detailed-design.md`
are the most concrete/current; `README.md` is an executive summary and may lag.

## Non-negotiable constraints (from the ADRs)

These are architectural decisions already made — don't re-litigate them, just follow them:

- **Never `subprocess` with `shell=True`.** Always pass command args as a list. This is the whole reason the rewrite exists (the bash scripts had shell-injection risk via string interpolation).
- **Never parse TOML with regex/grep/sed.** Use `tomllib` (stdlib, Python 3.11+).
- **No parent-shell environment mutation.** Don't export env vars for the calling shell to pick up; write `.env-services` files instead (preserves old behavior) and pass env explicitly to subprocesses.
- **No `self-update` command.** Deliberately omitted; users run `pip install --upgrade oarepo-cli` instead.
- **Dependency injection around subprocess/filesystem/env/network.** Business logic depends on protocols (`ProcessExecutor`, `FileSystem`, `EnvironmentProvider`), not concrete implementations — this is what makes the fake-based test pyramid in `02-testing-strategy.md` possible. Don't call `subprocess.run` or `Path.write_text` directly from services/CLI code.
- **Single `oarepo-cli` executable** with `library`, `repository` subcommand groups plus a top-level `repo-install`, built with Typer.
- **No premature abstraction.** Only introduce a protocol/abstraction when there are 2+ concrete implementations (real + fake counts).
- **Preserve exit codes, stdout/stderr, flag names, and `.env-services` file format exactly** — this is a behavior-preserving rewrite, not a redesign. See the compatibility matrix in `00-main-architecture.md` §1 and §8/§Compatibility Matrix (main doc + README).

## Dev commands

Only `pytest` is currently wired up (ruff/ty/pre-commit are planned in
implementation-steps.md Phase 0, not yet configured in this repo):

```bash
pip install -e ".[dev,tests]"
pytest
```

When Phase 0 lands, prefer whatever `ruff check` / `ty check` / `pytest` config it
adds over inventing new tooling.

## Tools

Use:
- git
- gh
- uv for the Python package manager

### Reading PR review comments in this repository

When you are working on a branch and need to check for new comments in the associated PR (target branch: `cli-as-python`), use these commands:

```bash
# 1. Find the PR number for your current branch
git remote get-url origin | sed 's/.*github.com\///' | sed 's/\.git$//'
gh pr list --state open -R oarepo/oarepo-cli --json number,headRefName

# 2. Get inline file comments (most common type of review feedback)
# Replace <PR_NUMBER> with the actual number from step 1
gh api repos/oarepo/oarepo-cli/pulls/<PR_NUMBER>/comments
```

The API endpoint returns JSON with `path`, `line`, `original_line`, and `body` fields, which tell you exactly which file and line the comment refers to.

**Example:** If the output shows a comment on `pyproject.toml` at line 43, read that file and look for the specific issue mentioned in `body`.

## Conventions

- Python 3.14 (`requires-python = ">=3.14,<3.15"` in `pyproject.toml`).
- License headers: every source file uses the simplified SPDX format:
  ```python
  # SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
  # SPDX-License-Identifier: MIT
  ```
  Plus `from __future__ import annotations` at the top of each file.
- Follow `implementation-steps.md`'s status flags when checking off work:
  `[ ]` not started, `[~]` in progress, `[x]` done (code + tests passing), `[!]` blocked.
