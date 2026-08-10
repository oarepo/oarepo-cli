# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for scripts/library_run.sh wrapper script."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_library_run_script_exists():
    """Verify the library_run.sh script exists and is executable."""
    script_path = Path(__file__).parent.parent.parent / "oarepo_cli" / "scripts" / "library_run.sh"
    assert script_path.exists(), f"Script not found at {script_path}"
    assert script_path.stat().st_mode & 0o111, f"Script is not executable: {script_path}"


def test_library_run_script_has_correct_shebang():
    """Verify the script has proper bash shebang."""
    script_path = Path(__file__).parent.parent.parent / "oarepo_cli" / "scripts" / "library_run.sh"
    with script_path.open() as f:
        first_line = f.readline().strip()
    assert first_line == "#!/usr/bin/env bash", f"Invalid shebang: {first_line}"


def test_library_run_script_syntax() -> None:
    """Verify the script has valid bash syntax (if bash is available)."""
    script_path = Path(__file__).parent.parent.parent / "oarepo_cli" / "scripts" / "library_run.sh"

    # Try to check syntax with bash -n
    result = subprocess.run(  # noqa: S603 - just a test, not a security issue to run the program
        ["bash", "-n", str(script_path)],  # noqa: S607 bash is ok
        capture_output=True,
        text=True,
        check=False,  # asserted later
    )

    assert result.returncode == 0, f"Bash syntax error:\n{result.stderr}"
