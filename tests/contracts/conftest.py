# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

import pytest

from oarepo_cli.services.process import ProcessExecutor


@pytest.fixture(params=["subprocess", "fake"])
def executor(request) -> ProcessExecutor:
    """Parametrized fixture that provides each ProcessExecutor implementation.

    This fixture runs dependent tests once per implementation, allowing
    contract tests to verify that both real and fake implementations
    satisfy the ProcessExecutor protocol.

    Args:
        request: Pytest request object with param value

    Returns:
        ProcessExecutor instance (SubprocessExecutor or FakeProcessExecutor)
    """
    if request.param == "subprocess":
        # Subprocess executor will be implemented in Step 0.5
        # For now, skip this parameter
        pytest.skip("SubprocessExecutor not yet implemented")

    from tests.fakes import FakeProcessExecutor

    return FakeProcessExecutor()
