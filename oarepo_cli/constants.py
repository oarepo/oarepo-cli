# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Application-wide constants."""

from __future__ import annotations

import re

# Python versions supported by the CLI (highest first for efficiency)
KNOWN_PYTHON_VERSIONS = ["3.14"]

# OARepo version to compatible Python versions mapping
# Based on the old library_runner.sh implementation
OAREPO_PYTHON_COMPATIBILITY = {
    14: ["3.14"],
    # Add more versions as they become available:
    # 13: ["3.12", "3.13"],
    # 12: ["3.10", "3.11", "3.12"],
}

# Default environment variables for streaming subprocess output
STREAM_ENV_DEFAULTS = {"PYTHONUNBUFFERED": "1"}

# Regex pattern for extracting OARepo major versions from dependency specifiers
OAREPO_VERSION_RE = re.compile(r"oarepo(\d+)")
