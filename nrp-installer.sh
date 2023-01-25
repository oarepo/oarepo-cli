#!/bin/bash

set -e

# TODO: find python
PYTHON=python3.9

if [ x"$1" == "x" ] ; then
  echo "Usage: $0 <target-project-directory>"
  exit 1
fi

PROJECT_DIR="$1"
OAREPO_CLI_INITIAL_VENV="$PROJECT_DIR/.venv/oarepo-cli-initial"

test -d "$PROJECT_DIR" || {
  mkdir "$PROJECT_DIR"
}

test -d "$PROJECT_DIR/.venv" || {
  mkdir "$PROJECT_DIR/.venv"
}

test -d "$OAREPO_CLI_INITIAL_VENV" || {
  "$PYTHON" -m venv "$OAREPO_CLI_INITIAL_VENV"
  "$OAREPO_CLI_INITIAL_VENV/bin/pip" install -U setuptools pip wheel
  "$OAREPO_CLI_INITIAL_VENV/bin/pip" install "git+https://github.com/oarepo/oarepo-cli"
}

"$OAREPO_CLI_INITIAL_VENV/bin/oarepo-cli" initialize "$PROJECT_DIR"
