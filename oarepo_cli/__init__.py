#
# Copyright (c) 2025 CESNET z.s.p.o.
#
# This file is a part of oarepo-cli (see https://github.com/oarepo/oarepo-cli).
#
# oarepo-cli is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.
#
"""A set of extensions to invenio-cli module."""

from __future__ import annotations

from .extensions import register_commands

__version__ = "13.0.0dev1"
"""Version string."""

__all__ = ("__version__", "register_commands")
