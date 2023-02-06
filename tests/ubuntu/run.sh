#!/bin/bash

set -e
cd $(dirname $0)

TEST_DATA_DIR=$(pwd)

# root part
./root.sh

if [ -f $TEST_DATA_DIR/env.sh ] ; then
    cp $TEST_DATA_DIR/env.sh /home/repo/repo_env.sh
fi

# repo user part
sudo -i -u repo /bin/bash $TEST_DATA_DIR/repo.sh
