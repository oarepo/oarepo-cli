# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Record model management via copier, for OARepo repository projects."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import copier
import yaml

from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services.repository import install_repository
from oarepo_cli.ui import ConsoleOutput

if TYPE_CHECKING:
    from pathlib import Path

    from oarepo_cli.core.context import ProjectContext


def _relative_to_root(path: Path, root: Path) -> Path:
    """Convert an answers-file path to be relative to root, as copier requires.

    copier's ``answers_file`` parameter must be relative to ``dst_path``
    (it raises a validation error otherwise); callers of ``ModelManager``
    may reasonably pass an absolute path or one relative to the current
    working directory, so resolve both sides before computing the relative
    path (``walk_up=True`` handles a config file living outside the
    repository root too, e.g. in a temp directory).
    """
    return path.resolve().relative_to(root.resolve(), walk_up=True)


def _load_yaml_data(path: Path) -> dict[str, Any]:
    """Load a YAML answers/data file into a dict, the same way copier's own
    ``--data-file`` CLI flag does (``copier._cli.py:data_file_switch``).

    PyYAML isn't declared directly in oarepo-cli's own dependencies, but
    it's a direct (not merely transitive) dependency of ``copier`` itself,
    for this exact purpose -- if it ever went away, copier's own
    ``--data-file`` would break too, so relying on it here is safe.
    """
    with path.open("rb") as f:
        return yaml.safe_load(f) or {}


class ModelManager:
    """Creates and updates OARepo record models via the copier Python API.

    Mirrors ``repository_runner.sh``'s ``create_model()``/``update_model()``
    functions, but invokes copier directly as a library
    (``copier.run_copy``/``copier.run_update``) using this venv's own
    installed ``copier`` + ``copier-template-extensions`` rather than
    shelling out to ``uvx --with ... copier ...`` for a fresh ephemeral
    environment on every call.

    One deliberate behavioral difference from the bash version: a given
    config/answers file is loaded and passed to copier as ``data`` (like
    copier's own ``--data-file``), not merely as ``answers_file`` (like
    bash's ``--answers-file``). ``answers_file`` alone only pre-fills
    copier's interactive prompts with prior answers -- it still requires a
    live terminal to confirm each one. Since the entire point of passing a
    config file here is scripted/non-interactive use, seeding ``data``
    (which copier answers from directly, without prompting) is required for
    that to actually work.
    """

    def __init__(self, context: ProjectContext, *, quiet: bool = False) -> None:
        """Initialize the model manager.

        Args:
            context: Project context with paths and configuration
            quiet: If True, suppress status/progress messages
        """
        self._context = context
        self._quiet = quiet

    def create_model(self, name: str, config_file: Path | None = None) -> None:
        """Create a new record model from the model copier template.

        Mirrors ``repository_runner.sh``'s ``create_model()``: renders the
        configured model template (``[tool.oarepo-cli] model.template_url``/
        ``.template_version``, default
        https://github.com/oarepo/nrp-model-copier @ rdm-14) into the
        repository root -- the template itself places generated files under
        ``models/<name>/``. If a virtual environment already exists, the
        repository is reinstalled afterwards (a new model changes entry
        points/dependencies in ``pyproject.toml``).

        Args:
            name: Model name (passed to the template as ``model_name``)
            config_file: Optional path to a YAML answers/data file. When
                given, its content seeds all answers (it must supply
                ``model_name`` itself, matching ``repository_runner.sh``,
                which doesn't also pass ``-d model_name=`` in this case);
                when omitted, only ``model_name`` is passed and the
                template's own defaults/prompts apply.

        Raises:
            ConfigurationError: If config_file is given but doesn't exist
        """
        if config_file is not None and not config_file.exists():
            raise ConfigurationError(f"Missing model config file: {config_file}")

        console = ConsoleOutput(quiet=self._quiet)
        template = self._context.config.model.template_url
        version = self._context.config.model.template_version
        is_github = template.startswith("https://")

        console.info(f"→ Creating model '{name}' from {template}\n")

        data = _load_yaml_data(config_file) if config_file is not None else {"model_name": name}
        copier.run_copy(
            template,
            self._context.root_directory,
            data=data,
            vcs_ref=version if is_github else None,
            unsafe=True,
            quiet=self._quiet,
        )

        if self._context.venv_path.exists():
            console.info("→ Reinstalling repository with the new model\n")
            install_repository(self._context, quiet=self._quiet)

        console.success(f"✓ Model '{name}' created successfully.\n")
        console.warning(
            "\nTo create the necessary database tables and search indices for "
            "your new model, run: oarepo-cli repository reset\n"
            "NOTE: this will PURGE ALL EXISTING DATA in your containers!\n"
        )

    def update_model(self, name: str, answers_file: Path | None = None) -> None:
        """Update an existing record model from its recorded template.

        Mirrors ``repository_runner.sh``'s ``update_model()``: copier's own
        ``.copier-answers.yml`` (written under ``models/<name>/`` during
        ``create_model``) records which template/ref/answers were used, so
        update works from that alone unless a different answers file is
        explicitly given (e.g. to point at a local template copy instead of
        the originally recorded one). That file is used both to locate the
        template/ref to update from (``answers_file``, as in the bash
        version) and, unlike the bash version, to seed answers non-
        interactively (``data``) -- see the class docstring for why.

        Args:
            name: Model name (must already exist under ``models/<name>``)
            answers_file: Optional path to a different answers file

        Raises:
            ConfigurationError: If the model directory or answers file
                doesn't exist
        """
        model_dir = self._context.root_directory / "models" / name
        if not model_dir.is_dir():
            raise ConfigurationError(f"Model directory 'models/{name}' does not exist.")

        resolved_answers_file = model_dir / ".copier-answers.yml"
        if answers_file is not None:
            if not answers_file.exists():
                raise ConfigurationError(f"Model config file does not exist: {answers_file}")
            resolved_answers_file = answers_file

        if not resolved_answers_file.exists():
            raise ConfigurationError(f"Answers file '{resolved_answers_file}' does not exist.")

        console = ConsoleOutput(quiet=self._quiet)
        version = self._context.config.model.template_version

        console.info(f"→ Updating model '{name}' with answers file {resolved_answers_file}\n")

        copier.run_update(
            self._context.root_directory,
            data=_load_yaml_data(resolved_answers_file),
            answers_file=_relative_to_root(resolved_answers_file, self._context.root_directory),
            vcs_ref=version,
            conflict="inline",
            unsafe=True,
            # copier requires this for git-tracked destinations (which a
            # real OARepo repository always is): since the user can review
            # the change via `git diff` / conflict markers (conflict=
            # "inline") before committing, it's safe to skip its own
            # confirmation prompt. Without it, run_update always raises
            # "Enable overwrite to update a subproject."
            overwrite=True,
            quiet=self._quiet,
        )

        console.success(f"✓ Model '{name}' updated successfully.\n")
