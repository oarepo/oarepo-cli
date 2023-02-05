#!/bin/bash

set -e

# download oarepo-cli
curl -O https://raw.githubusercontent.com/oarepo/oarepo-cli/v11.0/nrp-installer.sh

# run the repo installer
bash nrp-installer.sh -p python3 repo --config ${TEST_DATA_DIR}/oarepo.yaml --no-input
