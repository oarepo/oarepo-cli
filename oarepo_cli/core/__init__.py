# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Core utilities for OARepo CLI."""

from __future__ import annotations

__all__ = [
    "ConfigurationError",
    "FileNotFoundError",
    "OARepoError",
    "PlatformDetector",
    "ProcessExecutionError",
    "ValidationError",
    "VersionMismatchError",
    "get_platform_detector",
    "safe_run",
]

from oarepo_cli.core.errors import (
    ConfigurationError,
    FileNotFoundError,
    OARepoError,
    ProcessExecutionError,
    ValidationError,
    VersionMismatchError,
    safe_run,
)
from oarepo_cli.core.platform import (
    PlatformDetector,
    get_platform_detector,
)
