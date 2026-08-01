# OARepo extensions to invenio-cli

This package provides extensions to the Invenio CLI for working with OARepo-based repositories.

## Usage

uvx --with oarepo-cli invenio-cli

## What extensions are included?

### `invenio-cli install`

An extra step is added to the `invenio-cli install` command to make sure that the
theme.less file contains all the components from less libraries.
