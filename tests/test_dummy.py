# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

from __future__ import annotations


def test_version():
    """Test that the package has a version defined."""
    from oarepo_cli import __version__

    assert __version__ is not None
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_dummy():
    """Create a dummy function for testing purposes."""
    assert True
