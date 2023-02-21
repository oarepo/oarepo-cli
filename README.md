# oarepo-cli

Work in progress.

## Repository project initialization

Download the file from 
`https://raw.githubusercontent.com/oarepo/oarepo-cli/v11.0/nrp-installer.sh`,
inspect it (always a good practice) and run `bash nrp-installer.sh <project_dir>`

## Roadmap

NRP client is meant to simplify:

**Site:**

* [x] get script for automatic installation
* [x] checking invenio prerequisites
* [x] bootstraping new repository site in development mode
    * [x] in 1 git contains all mode
    * [ ] in per-model, per-ui git submodule mode
* [x] including UI (webpack) compilation and collection of static assets
* [x] running development server
* [ ] initialization when oarepo-initialize is used on existing sources
    * [ ] create virtualenvs
    * [ ] setup db if not set up
    * [ ] setup indices if not set up

**Metadata model:**

* [x] adding metadata model
* [x] testing metadata model
* [x] installing metadata model into the site
* [x] updating alembic during the installation step
    * [x] handling empty migrations when model has not changed
* [x] initializing index during the installation step and reindexing data
* [x] importing (sample) data
* [ ] proxied models (that is, model that is built on index alias)

*Requests:*

* [x] installing requests
* [ ] adding request type & actions
    * [ ] using approval process libraries

*Expanded fields:*

* [x] installing support for expanded fields
* [ ] adding expanded fields
    * [ ] using libraries of expanded fields

*Files:*

* [x] installing support for files

*Custom fields:*

* [x] installing support for custom fields

*Relations:*

* [x] installing support for relations

**User interface for a metadata model:**

* [x] adding UI module
* [ ] generating initial UI layout from model
* [ ] installing UI module to the site
* [ ] scaffolding UI component (jinja and react)
* [ ] UI on proxied models

**Automated testing:**

* [ ] running unit tests for models
    * [x] per-model tests
    * [ ] running tests for all models
* [ ] unit tests for UI
    * [ ] per-ui tests
    * [ ] running tests for all models
* [ ] running tests for site
    * [ ] overall tests (can run server, https on index page works)
    * [ ] per-ui tests (ui is accessible, returns meaningful pages)

**Build and Deployment scenarios:**

* [ ] publishing packages to pypi/gitlab/...
    * [ ] in monorepo mode (single pypi package from all components)
    * [ ] in per-model, per-ui package mode

* [ ] creating docker/k8s image for the whole site

**Github/Gitlab integration:**

* [ ] support github actions
* [ ] support gitlab CI/CD
