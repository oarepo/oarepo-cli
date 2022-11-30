# oarepo-cli

Work in progress.

OARepo client is meant to simplify:

**Site:**

* [x] checking invenio prerequisites
* [x] bootstraping new repository site in development mode
    * [ ] in per-model, per-ui git submodule mode
* [x] including UI compilation
* [x] running development server

**Metadata model:**

* [x] adding metadata model
* [x] testing metadata model
* [x] installing metadata model to the site
* [x] updating alembic during the installation step
    * [x] handling empty migrations when model has not changed
* [x] initializing index during the installation step and reindexing data
* [x] importing (sample) data

*Requests:*
* [ ] switching on requests
* [ ] adding request type
    * [ ] using approval process libraries

*Expanded fields:*
* [ ] switching on support for expanded fields
* [ ] adding expanded fields
    * [ ] using libraries of expanded fields

**User interface for a metadata model:**

* [ ] adding UI module
* [ ] installing UI module to the site
* [ ] scaffolding UI component (jinja and react)

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
