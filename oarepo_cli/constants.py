# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Application-wide constants."""

from __future__ import annotations

import re

# Python versions supported by the CLI (highest first for efficiency)
KNOWN_PYTHON_VERSIONS = ["3.14", "3.13", "3.12", "3.11", "3.10"]

# Default environment variables for streaming subprocess output
STREAM_ENV_DEFAULTS = {"PYTHONUNBUFFERED": "1"}

# Regex pattern for extracting OARepo major versions from dependency specifiers
OAREPO_VERSION_RE = re.compile(r"oarepo(\d+)")
