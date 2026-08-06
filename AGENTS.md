# AGENTS.md

Instructions for AI coding agents (Claude Code and similar) working in this repository.

## Project state: in progress

This repo is being reworked from a thin `invenio-cli` extension into a standalone
Python CLI (`oarepo-cli`) that replaces three bash scripts (`library_runner.sh`,
`repository_runner.sh`, `repository_installer.sh`). **The target architecture is
fully designed in [`docs/architecture/`](./docs/architecture/) but mostly not yet
implemented.**

Do not assume any module named in the architecture docs (`core/context.py`,
`services/process.py`, `services/venv.py`, etc.) already exists — check first. When implementing a piece of the design, follow
[`docs/architecture/implementation-steps.md`](./docs/architecture/implementation-steps.md)
phase by phase; don't jump ahead to later phases' modules before their
dependencies (earlier phases) exist.

Before starting implementation of a new step, create a new branch from `cli-as-python` branch (note: you might be on a different branch / not up-to-date, so you need to switch and pull first) and implement the step there.

After implementing a step, create a PR with the changes and request a review. The target branch of the PR will be `cli-as-python`.

Mark the action items in implementation-steps.md correctly when working
on a step or finishing it.

## Where to look

| Need | Read |
|------|------|
| Orientation / executive summary of the whole design | [docs/architecture/README.md](./docs/architecture/README.md) |
| Feature inventory: every command/flag/env var the CLI must support, external tool deps, known issues in the old bash scripts | [docs/architecture/00-main-architecture.md](./docs/architecture/00-main-architecture.md) §1 |
| Design principles, ADRs (why Typer, why single executable, why no self-update, why no `shell=True`, why no parent-env mutation) | [00-main-architecture.md](./docs/architecture/00-main-architecture.md) §2, §8 |
| Target package layout, component diagrams, key interfaces (`process.py`, `VirtualEnvironmentManager`, `PyProjectReader`), CLI command code samples | [docs/architecture/01-detailed-design.md](./docs/architecture/01-detailed-design.md) |
| How to test what you write (unit/contract/workflow/integration/characterization layers, fakes, fixtures) | [docs/architecture/02-testing-strategy.md](./docs/architecture/02-testing-strategy.md) |
| Shell-to-Python command mapping, breaking changes, env var semantics that must be preserved | [docs/architecture/03-migration-guide.md](./docs/architecture/03-migration-guide.md) |
| **The actual step-by-step build plan** — work through this in order | [docs/architecture/implementation-steps.md](./docs/architecture/implementation-steps.md) |

If two docs seem to disagree, `implementation-steps.md` and `01-detailed-design.md`
are the most concrete/current; `README.md` is an executive summary and may lag.

**Keep README.md up to date**: When implementing or modifying CLI commands,
always update `README.md` to reflect the current functionality. The README serves
as user-facing documentation and must accurately describe all available commands,
options, and workflows.

## Non-negotiable constraints (from the ADRs)

These are architectural decisions already made — don't re-litigate them, just follow them:

- **Never `subprocess` with `shell=True`.** Always pass command args as a list. This is the whole reason the rewrite exists (the bash scripts had shell-injection risk via string interpolation).
- **Never parse TOML with regex/grep/sed.** Use `tomllib` (stdlib, Python 3.11+).
- **No parent-shell environment mutation.** Don't export env vars for the calling shell to pick up; write `.env-services` files instead (preserves old behavior) and pass env explicitly to subprocesses.
- **No `self-update` command.** Deliberately omitted; users run `pip install --upgrade oarepo-cli` instead.
- **No dependency injection for boundaries with only one real implementation.** Filesystem, environment-variable, and subprocess access call `pathlib.Path`/`os.environ`/`oarepo_cli.services.process` directly, with no `Protocol` to inject — a swappable interface only pays for itself once a second real implementation exists. Test these boundaries against real state instead: `tmp_path` for the filesystem, `monkeypatch` for environment variables, and `pytest-subprocess`'s `fake_process` fixture (patches `subprocess.Popen` process-wide) for workflow-level tests of services that shell out to slow external tools (`uv`, `docker-services-cli`, `copier`). Only reach for a `Protocol` + dependency injection when a boundary genuinely has 2+ real implementations to keep interchangeable — see `02-testing-strategy.md` §4 (Contract Tests).
- **No test classes.** Write tests as plain `test_*` functions in `test_*.py` modules, with shared setup in fixtures (`conftest.py` or module-level `@pytest.fixture`) — never `class Test...`.
- **Single `oarepo-cli` executable** with `library`, `repository` subcommand groups plus a top-level `new` (repository scaffolding), built with Typer.
- **No premature abstraction.** Only introduce a protocol/abstraction when there are 2+ concrete implementations (fake does not count).
- **Preserve exit codes, stdout/stderr, flag names, and `.env-services` file format exactly** — this is a behavior-preserving rewrite, not a redesign. See the compatibility matrix in `00-main-architecture.md` §1 and §8/§Compatibility Matrix (main doc + README).
- **Never** rename imports unless absolutely necessary, do not use pattern like `from oarepo_cli.core.errors import ConfigurationError as ConfigurationError`
- **Always** run the format & lint & type checkers (make check) after your changes, use "if TYPE_CHECKING: ..." for type checking-only imports
- **Always** add module-level docstrings
- **Do not use** imports inside a function/method unless absolutely necessary to break circular imports
- **Always check for existing library** before adding a new functionality as the library might have already the functionality implemented and tested. It is ok to add a new library if it significantly improves the functionality or maintainability of the code.

## Dev commands

Use `run.sh` for all dev tasks instead of invoking `pytest`/`ruff`/`ty` directly — it's a thin
wrapper that forwards to this project's own `oarepo-cli library` commands (dogfooding the CLI on
itself), creating/updating `.venv` via `uv` as needed.

```bash
./run.sh test               # pytest with coverage (installs [tests] extra)
./run.sh lint                # ruff check/format, license-header + future-annotations checks, ty check — auto-fixes what it can
./run.sh format               # ruff format + ruff check --fix
./run.sh check                # same checks as lint, read-only (no fixes applied) — run this before opening a PR
```

**Always run `./run.sh check` after making changes**, per the non-negotiable constraints below.

**Important**: Integration tests are very slow. If you are making changes that don't affect the CLI itself, consider skipping them. If not skipping, run just the single test that you need to run. They will be run
in full on testing servers, so it is safe to skip the previous ones.

## Tools

Use:
- git
- gh
- uv for the Python package manager
- make for dev workflows (test/lint/format/type-check/pre-commit) — see Dev commands above

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
- **TYPE_CHECKING imports**: Use this consistent pattern:
  ```python
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from pathlib import Path
      from oarepo_cli.core.context import ProjectContext

  # All runtime imports go here, after the TYPE_CHECKING block
  from oarepo_cli.services import process
  ```
  This keeps type-only imports (which cause circular import issues) clearly separated from runtime imports.
- **Test fixture naming**: Follow these conventions for pytest fixtures:
  - **Use descriptive names without prefixes** for most fixtures: `testlib_project`, `clean_testlib`, `test_context`, `lint_project`
  - **Use `mock_` prefix** only for fixtures that return Mock objects: `mock_context`, `mock_project_root`
  - **Use `clean_` prefix** for cleanup fixtures that set up and tear down state: `clean_testlib`, `clean_testrepo`
  - **Avoid generic names**: prefer `lint_project` over `project`, `test_context` over `context`
  - **Document what the fixture provides** in the docstring, especially for complex fixtures
  - Examples:
    ```python
    @pytest.fixture
    def mock_context(tmp_path: Path) -> Mock:
        """Create a mock ProjectContext for unit tests."""
        ...


    @pytest.fixture
    def clean_testlib(testlib_project: Path) -> Iterator[Path]:
        """Clean up testlib before and after each test."""
        ...


    @pytest.fixture
    def lint_project(tmp_path: Path) -> Path:
        """A minimal, lint-clean library project with a real venv."""
        ...
    ```
- Follow `implementation-steps.md`'s status flags when checking off work:
  `[ ]` not started, `[~]` in progress, `[x]` done (code + tests passing), `[!]` blocked.
