# `Local` folder

This folder contains your local packages. These might
be pypi packages that are cloned locally for development
or a local package that is not intended to be deployed
to pypi but used inside the repository.

## Creating packages

```bash
nrp local add <package-name> \
          [<github url>] [--branch branch] [--site sitename]
```

If `github url` is provided, the command will clone the github
and branch (default if not specified) to the `<package-name>`
directory.

If not, a cookiecutter is used, will ask a couple of questions
and create a local package

`--site` will install the package in editable mode into 
the selected site

## Installing packages

```bash
nrp local install <package-name> [sitename]
```

Installs the package to the given site. Site name can be omitted
if there is just one site in the monorepo

## Removing packages

```bash
nrp local uninstall <package-name> [--remove-directory]
```

Will uninstall the package from all sites 
and optionally remove the directory. Use with caution!
