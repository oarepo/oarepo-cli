#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
#
# CI entry point for oarepo-cli's own test/release pipeline.
# Normally in libraries we are using the scripts/library_run.sh
# Here we want to use the actual version of this library and not
# the published one, so that is the reason why this script
# looks different from the library_run.sh one.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

PYTHON_VERSION="${PYTHON_VERSION:-3.14}"

# CI runners (e.g. GitHub Actions) have no controlling terminal, which has
# been observed to make Typer/Rich's help-text rendering collapse down to an
# empty bordered box with no visible option text at all. COLUMNS/LINES alone
# (also pinned in tests/conftest.py) aren't enough to fix this reliably --
# Typer's own Rich console reads TERMINAL_WIDTH once at import time and
# passes it straight to Console(width=...), bypassing tty/COLUMNS detection
# entirely, so it has to be a real process env var already in place before
# Python (and therefore typer) is even imported -- too late to set from
# conftest.py itself. Exported here, before the final exec below, so it's
# inherited by every subprocess run.sh's oarepo-cli invocation spawns,
# including pytest.
export TERMINAL_WIDTH="${TERMINAL_WIDTH:-200}"
export COLUMNS="${COLUMNS:-200}"
export LINES="${LINES:-50}"
export PYTEST_ADDOPTS="-vvv"

if [ ! -d .venv ] ; then
    uv venv
    uv pip install -e .
fi
.venv/bin/oarepo-cli library "$@"
