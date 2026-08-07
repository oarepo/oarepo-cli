# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Lazy loading of bundled configuration template files via importlib.resources."""

from __future__ import annotations

from importlib import resources


def read_text(filename: str) -> str:
    """Read a bundled configuration template's contents.

    Templates (e.g. ``ruff.toml.tmpl``, ``ty.toml.tmpl``) are stored as real
    data files in this package rather than embedded as Python string
    constants, and are only read from disk when a caller actually needs them
    (e.g. `library lint`/`library format` writing them out to a target
    project) - not at import time.

    Template files use a ``.tmpl`` suffix (e.g. ``ruff.toml.tmpl``, not
    ``ruff.toml``) so tools like ruff/mypy don't mistake them for their own
    config when linting/type-checking oarepo-cli's own source under this
    package - a bare ``ruff.toml`` here would otherwise be auto-discovered
    as the active ruff config for this directory.

    Args:
        filename: Name of the file inside ``oarepo_cli.configuration`` (e.g. "ruff.toml.tmpl")

    Returns:
        The file's contents as text

    """
    return resources.files(__package__).joinpath(filename).read_text(encoding="utf-8")
