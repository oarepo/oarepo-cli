#!/bin/bash

set -e

COMMAND="$0"
PYTHON=python3.9
NRP_CLI_VERSION="release"

print_usage() {
  echo "Usage: ${COMMAND} [-p <python_bin>] [-b <nrp-client-version>] <target-project-directory>"
  exit 1
}

# process switches
while getopts 'hp:b:' c
do
  case $c in
    h) print_usage ;;
    p) PYTHON=$OPTARG ;;
    b) NRP_CLI_VERSION=$OPTARG ;;
  esac
done
shift $((OPTIND-1))

python_version_error() {
  echo "The specified Python version (${PYTHON}) could not be found."
  echo "To resolve this issue, either add Python 3.9 to your PATH environment variable, or specify the path to the Python binary using the '-p' option."
  exit 1
}

RESOLVED_PYTHON=$(readlink -f $(which "$PYTHON")) || python_version_error

if ! [ -x "$RESOLVED_PYTHON" ] ; then
  python_version_error
fi

if [ x"$1" == "x" ] ; then
  print_usage
fi

PROJECT_DIR="$1"
shift
NRP_CLI_INITIAL_VENV="$PROJECT_DIR/.venv/nrp-cli-initial"

test -d "$PROJECT_DIR" || {
  mkdir "$PROJECT_DIR"
}

test -d "$PROJECT_DIR/.venv" || {
  mkdir "$PROJECT_DIR/.venv"
}

test -d "$NRP_CLI_INITIAL_VENV" || {
  "$RESOLVED_PYTHON" -m venv "$NRP_CLI_INITIAL_VENV"
  "$NRP_CLI_INITIAL_VENV/bin/pip" install -U setuptools pip wheel

  if [ ${NRP_CLI_VERSION} == "release" ] ; then
    "$NRP_CLI_INITIAL_VENV/bin/pip" install "oarepo-cli>=11.1.0,<12"
  elif [ ${NRP_CLI_VERSION} == "maintrunk" ] ; then
    "$NRP_CLI_INITIAL_VENV/bin/pip" install "git+https://github.com/oarepo/oarepo-cli"
  else
    "$NRP_CLI_INITIAL_VENV/bin/pip" install "${NRP_CLI_VERSION}"
  fi
}

export NRP_CLI_VERSION=${NRP_CLI_VERSION}

echo "Running $NRP_CLI_INITIAL_VENV/bin/nrp initialize $PROJECT_DIR $*"

"$NRP_CLI_INITIAL_VENV/bin/nrp" initialize "$PROJECT_DIR" --python $PYTHON "$@"
