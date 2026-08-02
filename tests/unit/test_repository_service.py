# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for repository service module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from oarepo_cli.core.context import ProjectContext
from oarepo_cli.services import repository


@pytest.fixture
def mock_context(tmp_path: Path) -> Mock:
    """Create a mock ProjectContext with real directories."""
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    return context


def test_configure_local_ports_updates_invenio_private(tmp_path: Path) -> None:
    """Test that configure_local_ports updates .invenio.private correctly."""
    # Setup files
    invenio_private = tmp_path / ".invenio.private"
    invenio_private.write_text(
        "# Existing config\nsearch_port = 1234\nsome_other_setting = 'value'\n"
    )

    variables = tmp_path / "variables"
    variables.write_text(
        """
export INVENIO_OPENSEARCH_PORT=9200
export INVENIO_DATABASE_PORT=5432
export INVENIO_REDIS_PORT=6379
export INVENIO_RABBIT_PORT=5672
export INVENIO_S3_PORT=9000
export INVENIO_UI_PORT=5000
"""
    )

    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    # Run function
    repository.configure_local_ports(context, quiet=True)

    # Verify result
    content = invenio_private.read_text()
    assert "search_port = 9200" in content
    assert "db_port = 5432" in content
    assert "redis_port = 6379" in content
    assert "rabbitmq_port = 5672" in content
    assert "s3_port = 9000" in content
    assert "web_port = 5000" in content
    # Old port line should be removed
    assert "search_port = 1234" not in content
    # Other settings should be preserved
    assert "some_other_setting = 'value'" in content


def test_configure_local_ports_handles_missing_variables(tmp_path: Path) -> None:
    """Test that configure_local_ports handles missing variables gracefully."""
    invenio_private = tmp_path / ".invenio.private"
    invenio_private.write_text("# Existing config\n")

    variables = tmp_path / "variables"
    variables.write_text("# No port variables\nexport FOO=bar\n")

    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    # Should not raise, but should skip update
    repository.configure_local_ports(context, quiet=True)

    # Content should be unchanged (except no port variables added)
    content = invenio_private.read_text()
    assert "search_port" not in content


def test_configure_local_ports_raises_on_missing_files(tmp_path: Path) -> None:
    """Test that configure_local_ports raises FileNotFoundError if files are missing."""
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    with pytest.raises(FileNotFoundError, match=".invenio.private"):
        repository.configure_local_ports(context, quiet=True)

    # Create .invenio.private but not variables
    (tmp_path / ".invenio.private").write_text("")

    with pytest.raises(FileNotFoundError, match="variables"):
        repository.configure_local_ports(context, quiet=True)


def test_get_instance_path_returns_path(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test that get_instance_path returns the correct path."""
    from oarepo_cli.services import process

    mock_result = Mock(spec=process.ProcessResult)
    mock_result.stdout = "Some startup output\n/var/instance/path\n"

    mock_run_shell = Mock(return_value=mock_result)
    monkeypatch.setattr(
        "oarepo_cli.services.invenio_cli.run_invenio_shell",
        mock_run_shell,
    )

    result = repository.get_instance_path(mock_context)

    assert result == Path("/var/instance/path")
    # Verify correct Python code was executed
    call_args = mock_run_shell.call_args
    assert call_args is not None
    assert "print(app.instance_path, end='')" in call_args[0]


def test_ensure_instance_structure_creates_directory(tmp_path: Path) -> None:
    """Test that ensure_instance_structure creates the instance directory."""
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    instance_path = tmp_path / "instance"
    assert not instance_path.exists()

    repository.ensure_instance_structure(context, instance_path, quiet=True)

    assert instance_path.exists()
    assert instance_path.is_dir()


def test_ensure_instance_structure_creates_symlink(tmp_path: Path) -> None:
    """Test that ensure_instance_structure creates invenio.cfg symlink."""
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    # Create invenio.cfg in root
    invenio_cfg = tmp_path / "invenio.cfg"
    invenio_cfg.write_text("# Config file\n")

    instance_path = tmp_path / "instance"
    instance_path.mkdir()

    repository.ensure_instance_structure(context, instance_path, quiet=True)

    # Verify symlink was created
    symlink = instance_path / "invenio.cfg"
    assert symlink.exists()
    # On platforms without symlink support, it might be a copy
    content = symlink.read_text()
    assert "# Config file" in content


def test_ensure_instance_structure_idempotent(tmp_path: Path) -> None:
    """Test that ensure_instance_structure is idempotent."""
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    invenio_cfg = tmp_path / "invenio.cfg"
    invenio_cfg.write_text("# Config\n")

    instance_path = tmp_path / "instance"

    # Run twice
    repository.ensure_instance_structure(context, instance_path, quiet=True)
    repository.ensure_instance_structure(context, instance_path, quiet=True)

    # Should not raise
    assert instance_path.exists()
    assert (instance_path / "invenio.cfg").exists()
