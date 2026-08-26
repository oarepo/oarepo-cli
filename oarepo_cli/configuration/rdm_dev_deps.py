# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Print invenio-rdm-records' Jest devDependencies as ``name@version`` specs.

Reads the ``devDependencies`` from the bundled ``package.json`` of the
installed ``invenio_rdm_records`` and prints them space-separated on a
marker-prefixed line, ready to hand to ``pnpm add -D``. It only needs the
target project's environment (that is where ``invenio_rdm_records`` lives),
not a Flask app, but runs via ``services.repository.run_invenio_shell`` all
the same -- the marker lets the caller pick the result out of the app-boot
logging on stdout. Executed as text, not imported.
"""

from __future__ import annotations

import json
import pathlib

import invenio_rdm_records

MARKER = "OAREPO_RDM_DEV_DEPS:"

package_json_path = (
    pathlib.Path(invenio_rdm_records.__file__).parent / "assets/semantic-ui/js/invenio_rdm_records/package.json"
)

with package_json_path.open() as f:
    package_json = json.load(f)

dev_deps = package_json.get("devDependencies", {})

print(MARKER + " ".join(f"{name}@{version}" for name, version in dev_deps.items()))  # noqa: T201
