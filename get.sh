#!/bin/bash

set -e

# TODO: find python
PYTHON=python3.9

PROJECT_DIR="$1"

test -d "$PROJECT_DIR" || {
  mkdir "$PROJECT_DIR"
}

test -d "$PROJECT_DIR/.venv" || {
  mkdir "$PROJECT_DIR/.venv"
}

test -d "$PROJECT_DIR/.venv/oarepo-cli" || {
  "$PYTHON" -m venv "$PROJECT_DIR/.venv/oarepo-cli"
  "$PROJECT_DIR/.venv/oarepo-cli/bin/pip" install -U setuptools pip wheel
  "$PROJECT_DIR/.venv/oarepo-cli/bin/pip" install "git+https://github.com/oarepo/oarepo-cli"
}

"$PROJECT_DIR/.venv/oarepo-cli/bin/oarepo-initialize" "$PROJECT_DIR"
