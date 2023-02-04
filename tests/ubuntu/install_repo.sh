#!/bin/bash

set -e

cp $(dirname $0)/oarepo.yaml ~/

cd ~

# nodejs
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.3/install.sh | bash
export NVM_DIR=$HOME/.nvm
source $NVM_DIR/nvm.sh
nvm install v14
nvm use v14

# download oarepo-cli
curl -O https://raw.githubusercontent.com/oarepo/oarepo-cli/v11.0/nrp-installer.sh

# run the repo installer
bash nrp-installer.sh -p python3 repo --config oarepo.yaml --no-input

# run model installer

# compile the model

# install the model

# run the server on the background


