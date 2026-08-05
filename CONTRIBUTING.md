# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

## Types of Contributions

### Report Bugs

Report bugs at https://github.com/oarepo/oarepo-cli/issues.

If you are reporting a bug, please include:

- Your operating system name and version.
- Any details about your local setup that might be helpful in troubleshooting.
- Detailed steps to reproduce the bug.

### Fix Bugs

Look through the GitHub issues for bugs. Anything tagged "bug" is open to
whoever wants to implement it.

### Implement Features

Look through the GitHub issues for features, or [`docs/architecture/implementation-steps.md`](./docs/architecture/implementation-steps.md)
for the project's own step-by-step build plan — see [Where to look](./AGENTS.md#where-to-look)
in `AGENTS.md` for the full set of design docs behind it.

### Improve Documentation

`oarepo-cli` could always use more documentation, whether in `README.md`,
docstrings, or the architecture docs under `docs/architecture/`.

### Submit Feedback

The best way to send feedback is to file an issue at
https://github.com/oarepo/oarepo-cli/issues. If you're proposing a feature,
explain in detail how it would work and keep the scope as narrow as possible,
to make it easier to implement and review.

## Get Started

Ready to contribute? Here's how to set up `oarepo-cli` for local development.

1. Fork the `oarepo/oarepo-cli` repo on GitHub and clone your fork locally:

   ```console
   $ git clone git@github.com:your_name_here/oarepo-cli.git
   $ cd oarepo-cli
   ```

2. Install the development dependencies. This project uses [`uv`](https://docs.astral.sh/uv/)
   and a `Makefile` that installs the right dependency group automatically:

   ```console
   $ make install-dev    # ruff, ty, pre-commit
   $ make pre-commit-setup
   ```

3. **Create a branch off `cli-as-python`, not `main`** — this repository is
   mid-rewrite (see `AGENTS.md`), and `cli-as-python` is the integration
   branch all work targets until the rewrite is complete:

   ```console
   $ git fetch origin
   $ git checkout cli-as-python
   $ git pull
   $ git checkout -b your-branch-name
   ```

   If you're picking up a step from `implementation-steps.md`, name the
   branch after it (e.g. `step-5.2-repository-installation-workflow`).

4. Make your changes locally, following the conventions in `AGENTS.md`
   (SPDX license headers, `from __future__ import annotations`, no
   `shell=True`, no test classes, etc.) — read it before your first PR.

5. Run the checks and the test suite:

   ```console
   $ make check   # lint + format + type-check
   $ make test    # pytest with coverage
   ```

   Integration tests are slow; if you're only touching one area, run just
   the relevant test file instead of the full suite while iterating.

6. Commit your changes. This project uses [Conventional Commits](https://www.conventionalcommits.org/)
   (`fix:`, `feat:`, `refactor:`, `docs:`, `test:`, ...), imperative mood,
   explaining *why* over *what*:

   ```console
   $ git add <files>
   $ git commit -m "fix: short summary of the change"
   ```

7. Push your branch and open a pull request **against `cli-as-python`**, not
   `main`:

   ```console
   $ git push -u origin your-branch-name
   ```

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests and must not decrease test coverage.
2. `make check` and `make test` both pass.
3. If the pull request changes user-facing behavior, `README.md` is updated
   to match.
4. If the pull request implements or finishes a step from
   `docs/architecture/implementation-steps.md`, its checklist items are
   marked accordingly (`[x]` done, `[~]` in progress, `[!]` blocked).
5. New public and private functions/classes have a docstring explaining
   what they do and, where it isn't obvious from the code, why.

## Code Style

- Python 3.14 only, `ruff` for linting/formatting, `ty` for type checking —
  `make check` runs all three.
- Never `subprocess` with `shell=True`; always pass argument lists.
- No test classes — plain `test_*` functions, with shared setup in fixtures.
- Every source file starts with an SPDX header and `from __future__ import annotations`:

  ```python
  # SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
  # SPDX-License-Identifier: MIT

  from __future__ import annotations
  ```

See `AGENTS.md` for the complete set of conventions and non-negotiable
constraints, and `docs/architecture/02-testing-strategy.md` for this
project's testing philosophy (unit vs. integration, fakes vs. real tools).

## License

By contributing, you agree that your contributions will be licensed under
the [MIT License](LICENSE).
