#!/bin/bash

set -e

# download oarepo-cli
curl -O https://raw.githubusercontent.com/oarepo/oarepo-cli/v11.0/nrp-installer.sh

# run the repo installer
bash nrp-installer.sh -p python3 repo --config ${TEST_DATA_DIR}/oarepo.yaml --no-input


# patch invenio

# max recursion error in template when invenio-administration templates are registered before invenio-theme templates
find repo -path '**/invenio_administration/templates/semantic-ui/invenio_theme/header_login.html' | while read ; do
  mv $REPLY $(dirname $REPLY)/administration_header_login.html
done