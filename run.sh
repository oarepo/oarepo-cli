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

if [ ! -d .venv ] ; then
    uv venv
    uv pip install -e .
fi
.venv/bin/oarepo-cli library "$@"
