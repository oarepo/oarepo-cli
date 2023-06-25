#! /bin/bash

set -e

usage() { echo "Usage: $0 [-d to run everything in docker] repo_input_directory repo_output_directory"; }

SERVER_PID=
kill_server() {
  if [ -z "$SERVER_PID" ] ; then
    return
  fi
  SERVER_PGID=$(ps opgid= "$SERVER_PID" | tr -d ' ')
  if [ ! -z "$SERVER_PGID" ] ; then
    echo "killing pid $1, group $SERVER_PGID"
    kill  -- -$SERVER_PGID
    sleep 2
  fi
  SERVER_PID=
}

trap 'kill_server' EXIT

USE_DOCKER='--outside-docker'

while getopts "dh" o; do
    case "${o}" in
        d)
            USE_DOCKER='--use-docker'
            ;;
        h)
            usage
            exit 0
            ;;
        *)
            usage
            exit 1
            ;;
    esac
done
shift $(($OPTIND - 1))

if [[ $# = 0 ]] ; then
  echo "First argument must be the input repository config directory"
  exit 1
fi

REPO_INPUT_DIRECTORY=$1
shift

if [[ $# -gt 0 ]] ; then
  REPO_OUTPUT_DIRECTORY=$1
else
  REPO_OUTPUT_DIRECTORY=/tmp/repo
fi

echo "Running tests from $REPO_INPUT_DIRECTORY, will use $REPO_OUTPUT_DIRECTORY, docker is set up to $USE_DOCKER"

#if [ -d $REPO_OUTPUT_DIRECTORY ] ; then
#  echo "output directory already exists, please select a different one"
#  exit 1
#fi
#
#nrp initialize --config $REPO_INPUT_DIRECTORY/oarepo.yaml \
#    $REPO_OUTPUT_DIRECTORY $USE_DOCKER --no-input
#
#nrp site add mysite \
#    --project-dir $REPO_OUTPUT_DIRECTORY \
#    $USE_DOCKER --no-input

#nrp run $USE_DOCKER \
#    --project-dir $REPO_OUTPUT_DIRECTORY &
#SERVER_PID=$!
#
## pause to let it boot up
#sleep 2
#curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/
#
#kill_server

# now install model
#nrp model add mymodel \
#    --project-dir $REPO_OUTPUT_DIRECTORY \
#    $USE_DOCKER --no-input
#
#nrp model compile mymodel \
#    --project-dir $REPO_OUTPUT_DIRECTORY \
#    $USE_DOCKER --no-input

#nrp model install mymodel \
#    --project-dir $REPO_OUTPUT_DIRECTORY \
#    $USE_DOCKER --no-input
#
#nrp run $USE_DOCKER \
#    --project-dir $REPO_OUTPUT_DIRECTORY &
#SERVER_PID=$!
#
## pause to let it boot up
#sleep 5
#curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/api/mymodel/
#
#kill_server

#nrp ui add myui \
#    --project-dir $REPO_OUTPUT_DIRECTORY \
#    $USE_DOCKER --no-input
#
#nrp ui install myui \
#    --project-dir $REPO_OUTPUT_DIRECTORY \
#    $USE_DOCKER --no-input

nrp run $USE_DOCKER \
    --project-dir $REPO_OUTPUT_DIRECTORY &
SERVER_PID=$!

# pause to let it boot up
sleep 5
curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/myui/

kill_server
