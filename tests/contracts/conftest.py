# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

import pytest

from oarepo_cli.services.process import ProcessExecutor


@pytest.fixture
def executor() -> ProcessExecutor:
    """Provide the SubprocessExecutor for contract tests.

    Returns:
        SubprocessExecutor instance for testing
    """
    from oarepo_cli.adapters.subprocess_executor import SubprocessExecutor

    return SubprocessExecutor()
