#! /bin/bash

set -e

usage() { echo "Usage: $0 [-d to run everything in docker] repo_input_directory repo_output_directory"; }

SERVER_PID=

kill_server() {
  if [ ! -z "$1" ] ; then
    nrp kill "$1"
  fi
  SERVER_PID=
}

trap 'kill_server "$SERVER_PID"' EXIT

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

if [ -d $REPO_OUTPUT_DIRECTORY ] ; then
  echo "output directory already exists, please select a different one"
  exit 1
fi

echo ">>> initialize"
nrp initialize --config $REPO_INPUT_DIRECTORY/oarepo.yaml \
    $REPO_OUTPUT_DIRECTORY $USE_DOCKER --no-input

echo ">>> add mysite"
nrp site add mysite \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input

echo ">>> run and check that mysite homepage is ok"
nrp run $USE_DOCKER \
    --project-dir $REPO_OUTPUT_DIRECTORY &
SERVER_PID=$!

# pause to let it boot up
sleep 2
curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/

kill_server $SERVER_PID


echo ">>> add model"
nrp model add mymodel \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input

echo ">>> compile model"
nrp model compile mymodel \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input

echo ">>> install model"
nrp model install mymodel \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input

echo ">>> check that listing is ok"
nrp run $USE_DOCKER \
    --project-dir $REPO_OUTPUT_DIRECTORY &
SERVER_PID=$!

# pause to let it boot up
sleep 5
curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/api/mymodel/
echo ">>> TODO: add record via api"
echo ">>> TODO: check that the record is in listing"
echo ">>> TODO: check that the record is on GET"

kill_server  $SERVER_PID

echo ">>> add ui for the model"
nrp ui add myui \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input

echo ">>> install the ui"
nrp ui install myui \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input

echo ">>> check that the UI listing page works"
nrp run $USE_DOCKER \
    --project-dir $REPO_OUTPUT_DIRECTORY &
SERVER_PID=$!

# pause to let it boot up
sleep 5
curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/myui/

echo ">>> check that the UI listing contains the sample record"
echo ">>> check that the UI detail of the record exists"
kill_server  $SERVER_PID

# remove the ui and check that we get 404
echo ">>> remove the ui"
nrp ui uninstall myui \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input
rm -rf $REPO_OUTPUT_DIRECTORY/ui/myui

echo ">>> check that the UI listing page is not accessible anymore"
nrp run $USE_DOCKER \
    --project-dir $REPO_OUTPUT_DIRECTORY &
SERVER_PID=$!

# pause to let it boot up
sleep 5
 homepage should work
curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/

err_code=$(curl -k -s -o /dev/null -w "%{http_code}" --retry 5 --retry-all-errors https://localhost:5000/myui/)
if [ "$err_code" != "404" ] ; then
  echo "UI Listing shoud return 404, got $err_code"
  exit 1
fi

echo ">>> check that the detail page is not accessible anymore"

kill_server  $SERVER_PID

echo ">>> remove the model"
nrp model uninstall mymodel \
    --project-dir $REPO_OUTPUT_DIRECTORY \
    $USE_DOCKER --no-input
rm -rf $REPO_OUTPUT_DIRECTORY/models/mymodel

echo ">>> check that listing no more exists"
nrp run $USE_DOCKER \
    --project-dir $REPO_OUTPUT_DIRECTORY &
SERVER_PID=$!

# pause to let it boot up
sleep 5
# homepage should still be ok
curl -k --retry 5 --retry-all-errors --fail-with-body https://localhost:5000/

err_code=$(curl -k -s -o /dev/null -w "%{http_code}" --retry 5 --retry-all-errors https://localhost:5000/api/mymodel)
if [ "$err_code" != "404" ] ; then
  echo "API Listing shoud return 404, got $err_code"
  exit 1
fi

kill_server  $SERVER_PID
