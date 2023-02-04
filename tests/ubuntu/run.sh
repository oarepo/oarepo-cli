#!/bin/bash

set -e
cd $(dirname $0)

# download software
./prepare_as_root.sh

# install the repo and start it
sudo -i -u repo -- bash ./install_repo.sh

# run tests
