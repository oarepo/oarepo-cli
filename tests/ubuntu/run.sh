#!/bin/bash

set -e
cd $(dirname $0)

TEST_DATA_DIR=$(pwd)

# root part
./root.sh

# repo user part
sudo -i -u repo /bin/bash $TEST_DATA_DIR/repo.sh
