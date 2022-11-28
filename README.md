# oarepo-cli

Work in progress.

OARepo client is meant to simplify:

**Site:**

* [x] checking invenio prerequisites
* [x] bootstraping new repository site in development mode
    * [x] in monorepo mode
    * [ ] in per-model, per-ui package mode
    * [ ] in per-model, per-ui git submodule mode
* [x] including UI compilation
* [ ] running development server

**Metadata model:**

* [x] adding metadata model
* [x] testing metadata model
* [x] installing metadata model to the site
* [ ] updating alembic during the installation step

**User interface for a metadata model:**

* [ ] adding UI module
* [ ] installing UI module to the site

**Deployment scenarios:**

* [ ] publishing packages to pypi/gitlab/...
* [ ] creating docker/k8s image for the whole site

**Github/Gitlab integration:**

* [ ] support github actions
* [ ] support gitlab CI/CD
