# oarepo-cli runner scripts

These scripts are convenience wrappers around oarepo-cli commands. When copied to a library/repository,
the script will automatically upon the first run:

- create a .tools virtualenv
- install the latest version of oarepo-cli
- run the specified oarepo-cli command

In subsequent runs, the virtualenv will be reused.

## Library runner

When creating a new library, please copy the `library_run.sh` script to the root of your repository and rename it to `run.sh`.

## Repository runner

The repository installer will automatically copy the `repository_run.sh` into the `run.sh` script when the repository is installed.
