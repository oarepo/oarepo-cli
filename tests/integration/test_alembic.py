# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Integration tests for AlembicManager, against real pyproject.toml files.

AlembicManager only touches a project's pyproject.toml (via tomlkit) and
filesystem (creating alembic/ directories), so these tests exercise the real
tomlkit read/modify/write path against real tmp_path files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import tomlkit

from oarepo_cli.core.config import CliConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.errors import ValidationError
from oarepo_cli.services.alembic import AlembicManager
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from pathlib import Path

LIBRARY_PYPROJECT = """\
[project]
name = "mylib"
dependencies = [
    "oarepo>=14.0.0,<15.0.0",
]
requires-python = ">=3.14,<3.15"

[project.entry-points."invenio_db.models"]
mylib = "mylib.records.models"
"""

LIBRARY_PYPROJECT_NO_MODELS = """\
[project]
name = "mylib"
dependencies = [
    "oarepo>=14.0.0,<15.0.0",
]
requires-python = ">=3.14,<3.15"
"""


def make_context(root: Path) -> ProjectContext:
    return ProjectContext(
        root_directory=root,
        pyproject_path=root / "pyproject.toml",
        venv_path=root / ".venv",
        python_binary=root / ".venv" / "bin" / "python",
        oarepo_version=14,
        config=CliConfig(),
    )


@pytest.fixture
def lib_root(tmp_path: Path) -> Path:
    """Create a library root with src layout and invenio_db.models entrypoint."""
    root = tmp_path / "lib"
    root.mkdir()
    (root / "pyproject.toml").write_text(LIBRARY_PYPROJECT)
    (root / "src" / "mylib").mkdir(parents=True)
    return root


@pytest.fixture
def lib_root_flat_layout(tmp_path: Path) -> Path:
    """Create a library root with flat layout and invenio_db.models entrypoint."""
    root = tmp_path / "lib"
    root.mkdir()
    (root / "pyproject.toml").write_text(LIBRARY_PYPROJECT)
    (root / "mylib").mkdir(parents=True)
    return root


@pytest.fixture
def lib_root_no_models(tmp_path: Path) -> Path:
    """Create a library root without invenio_db.models entrypoint."""
    root = tmp_path / "lib"
    root.mkdir()
    (root / "pyproject.toml").write_text(LIBRARY_PYPROJECT_NO_MODELS)
    (root / "src" / "mylib").mkdir(parents=True)
    return root


def test_init_creates_alembic_directory_and_entrypoint(lib_root: Path) -> None:
    """init() creates alembic directory and adds entrypoint when missing."""
    context = make_context(lib_root)
    manager = AlembicManager(context, ConsoleOutput(quiet=True))

    manager.init()

    # Check directory was created
    alembic_dir = lib_root / "src" / "mylib" / "alembic"
    assert alembic_dir.exists()
    assert alembic_dir.is_dir()

    # Check entrypoint was added
    document = tomlkit.parse(context.pyproject_path.read_text())
    alembic_ep = document["project"]["entry-points"]["invenio_db.alembic"]
    assert "mylib" in alembic_ep
    assert alembic_ep["mylib"] == "mylib:alembic"


def test_init_flat_layout_creates_correct_entrypoint(lib_root_flat_layout: Path) -> None:
    """init() works with flat layout and creates correct entrypoint."""
    context = make_context(lib_root_flat_layout)
    manager = AlembicManager(context, ConsoleOutput(quiet=True))

    manager.init()

    # Check directory was created in flat layout
    alembic_dir = lib_root_flat_layout / "mylib" / "alembic"
    assert alembic_dir.exists()

    # Check entrypoint was added
    document = tomlkit.parse(context.pyproject_path.read_text())
    alembic_ep = document["project"]["entry-points"]["invenio_db.alembic"]
    assert alembic_ep["mylib"] == "mylib:alembic"


def test_init_idempotent_with_existing_directory(lib_root: Path) -> None:
    """init() is idempotent when alembic directory already exists."""
    context = make_context(lib_root)
    alembic_dir = lib_root / "src" / "mylib" / "alembic"
    alembic_dir.mkdir(parents=True)

    manager = AlembicManager(context, ConsoleOutput(quiet=True))
    manager.init()

    # Directory should still exist
    assert alembic_dir.exists()

    # Entrypoint should be added
    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "mylib" in document["project"]["entry-points"]["invenio_db.alembic"]


def test_init_idempotent_with_existing_entrypoint(lib_root: Path) -> None:
    """init() is idempotent when entrypoint already exists."""
    # Pre-add the entrypoint
    document = tomlkit.parse((lib_root / "pyproject.toml").read_text())
    project = document.setdefault("project", tomlkit.table())
    entrypoints = project.setdefault("entry-points", tomlkit.table())
    alembic_ep = entrypoints.setdefault("invenio_db.alembic", tomlkit.table())
    alembic_ep["mylib"] = "mylib:alembic"
    (lib_root / "pyproject.toml").write_text(tomlkit.dumps(document))

    context = make_context(lib_root)
    manager = AlembicManager(context, ConsoleOutput(quiet=True))

    manager.init()

    # Entrypoint should still be there
    document = tomlkit.parse(context.pyproject_path.read_text())
    alembic_ep = document["project"]["entry-points"]["invenio_db.alembic"]
    assert alembic_ep["mylib"] == "mylib:alembic"

    # Directory should be created
    alembic_dir = lib_root / "src" / "mylib" / "alembic"
    assert alembic_dir.exists()


def test_init_without_models_entrypoint_raises(lib_root_no_models: Path) -> None:
    """init() raises ValidationError when invenio_db.models entrypoint is missing."""
    context = make_context(lib_root_no_models)
    manager = AlembicManager(context, ConsoleOutput(quiet=True))

    with pytest.raises(ValidationError, match=r"No 'invenio_db\.models' entrypoint found"):
        manager.init()

    # No directory should be created
    alembic_dir = lib_root_no_models / "src" / "mylib" / "alembic"
    assert not alembic_dir.exists()

    # No entrypoint should be added
    document = tomlkit.parse(context.pyproject_path.read_text())
    assert "entry-points" not in document.get("project", {})


def test_init_preserves_existing_formatting(lib_root: Path) -> None:
    """Existing entrypoints in pyproject.toml survive the tomlkit round trip."""
    # Add a comment
    original = (lib_root / "pyproject.toml").read_text()
    original = "# This is my library\n" + original
    (lib_root / "pyproject.toml").write_text(original)

    context = make_context(lib_root)
    manager = AlembicManager(context, ConsoleOutput(quiet=True))

    manager.init()

    content = context.pyproject_path.read_text()
    assert "# This is my library" in content
    assert '[project.entry-points."invenio_db.models"]' in content


def test_init_uses_first_code_directory_for_alembic(lib_root: Path) -> None:
    """init() creates alembic directory in the first code directory."""
    context = make_context(lib_root)
    manager = AlembicManager(context, ConsoleOutput(quiet=True))

    # Get first code directory (without tests)
    first_code_dir = context.code_directories_without_tests[0]

    manager.init()

    # Check alembic was created in first code directory
    alembic_dir = first_code_dir / "mylib" / "alembic"
    assert alembic_dir.exists()
