# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Print a project's ``invenio_assets.webpack`` entry-point root directories.

Runs inside ``invenio shell`` (needs an application context: the webpack
bundle objects' ``.entry`` attribute resolves against ``current_app``). The
target distribution name is passed via the ``OAREPO_WEBPACK_PACKAGE``
environment variable. The result is printed on a marker-prefixed line so the
caller can pick it out of invenio shell's own logging on stdout.

Executed as text via ``services.repository.run_invenio_shell`` -- it is not
imported as a module, so the discovery runs at import time by design.
"""

from __future__ import annotations

import os

try:
    import importlib_metadata
except ImportError:  # pragma: no cover - importlib_metadata is a backport
    import importlib.metadata as importlib_metadata

MARKER = "OAREPO_WEBPACK_ENTRIES:"


def _flatten(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for element in value for item in _flatten(element)]
    return []


dist = importlib_metadata.distribution(os.environ["OAREPO_WEBPACK_PACKAGE"])

entry_files = [
    entry
    for ep in dist.entry_points
    if ep.group == "invenio_assets.webpack"
    for value in ep.load().entry.values()
    for entry in _flatten(value)
]

# Keep only the outermost roots (drop any path nested under another entry),
# then the common parent directory of each.
common_roots = {
    # Deliberately string ops, not pathlib: these are "./"-relative webpack
    # paths and the caller relies on the leading "./" being preserved.
    os.path.dirname(path)  # noqa: PTH120
    for path in entry_files
    if not any(path != other and path.startswith(other.rstrip("/") + "/") for other in entry_files)
}

print(MARKER + ",".join(sorted(root for root in common_roots if root)))  # noqa: T201
