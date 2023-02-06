#! /bin/bash
set -e

if [ -f ~/repo_env.sh ] ; then
    source ~/repo_env.sh
fi

export TEST_DATA_DIR=$(dirname $0)

echo "Installing the repo"
$TEST_DATA_DIR/install-repo.sh

echo "Starting the server"
$TEST_DATA_DIR/start-server.sh

echo "Getting homepage"
$TEST_DATA_DIR/test-homepage.sh

echo "Stopping the server"
$TEST_DATA_DIR/stop-server.sh

# TODO: install a model, create user, get token, insert the data, etc...
