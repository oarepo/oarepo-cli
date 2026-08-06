#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT
#
# temporary CI entry point for oarepo-cli's own test/release pipeline (.github/workflows,
# via oarepo/oarepo's reusable workflows and .github/actions/{install_dependencies,
# pytest,jstest}).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}"

PYTHON_VERSION="${PYTHON_VERSION:-3.14}"

if [ ! -d .venv ] ; then
    uv venv
    uv pip install -e .
fi
.venv/bin/oarepo-cli library "$@"
