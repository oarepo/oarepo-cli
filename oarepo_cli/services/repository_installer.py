# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Repository installer: scaffolds a brand-new repository from a copier template."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import copier
import yaml

from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services import process
from oarepo_cli.services.process import ProcessOutputMode
from oarepo_cli.ui import ConsoleOutput  # noqa: TC001 (used at runtime, not just type hints)

DEVELOPMENT_CERT_SUBJECT = "/C=CH/ST=./L=./O=./OU=./CN=localhost/emailAddress=."


def _load_yaml_data(path: Path) -> dict[str, Any]:
    """Load a YAML answers/data file into a dict, the same way copier's own
    ``--data-file`` CLI flag does (``copier._cli.py:data_file_switch``),
    matching ``services.models._load_yaml_data``'s same rationale.
    """
    with path.open("rb") as f:
        return yaml.safe_load(f) or {}


class RepositoryInstaller:
    """Scaffolds a brand-new repository from a copier template.

    Mirrors ``repository_installer.sh``'s ``create_repository()`` and the
    setup steps that follow it (SSL certificate generation, a Docker
    Compose cleanup, git initialization), but invokes copier directly as a
    library (``copier.run_copy``) using this venv's own installed
    ``copier`` + ``copier-template-extensions``, exactly the approach
    ``services.models.ModelManager`` already uses for model templates --
    rather than shelling out to ``uvx --python <python_binary> --with
    copier-template-extensions --with pycountry copier copy ...`` for a
    fresh ephemeral environment on every call.

    One consequence: the ``--python``/``--uv``/``--uvx`` options on
    ``cli.installer.new_repository`` no longer select which
    interpreter/tool actually runs copier -- they're still validated there
    for interface compatibility with the shell script (a missing binary is
    still reported clearly, before anything else runs) but aren't forwarded
    here, since there's no longer a separate copier process to run them
    with.
    """

    def __init__(self, console: ConsoleOutput) -> None:
        """Initialize the repository installer.

        Args:
            console: Console output handler for status messages
        """
        self._console = console

    def install(
        self,
        name: str,
        *,
        template: str,
        version: str,
        config_file: Path | None = None,
    ) -> Path:
        """Create a new repository from ``template`` in ``./<name>``.

        Mirrors ``repository_installer.sh``'s ``create_repository()`` plus
        everything that follows it in the script: SSL certificate
        generation, a best-effort ``docker compose down`` for any stale
        containers from a previous attempt at this name, and git
        initialization (skipped in CI or without git installed).

        Args:
            name: Repository name -- both the copier ``repository_name``
                answer (always passed, matching the shell script's own
                unconditional ``-d repository_name=`` even when
                ``--config``/``--data-file`` is also given) and the
                destination directory, created relative to the current
                working directory (matching the shell script)
            template: A GitHub URL (rendered with ``vcs_ref=version``) or a
                local path (``version`` is ignored, matching copier's own
                behavior for non-VCS templates)
            version: Template git ref, used only when ``template`` is a
                GitHub URL
            config_file: Optional YAML data file seeding all answers (see
                ``services.models.ModelManager.create_model``'s docstring
                for why this is passed as copier's ``data``, not merely
                ``answers_file``)

        Returns:
            Path to the created repository (``./<name>``, resolved)

        Raises:
            ConfigurationError: If config_file is given but doesn't exist
        """
        if config_file is not None and not config_file.exists():
            raise ConfigurationError(f"Missing repository config file: {config_file}")

        target_dir = Path.cwd() / name
        is_github = template.startswith("https://")

        self._console.info(f"→ Creating repository '{name}' from {template}\n")

        # copier's quiet flag controls its own output
        quiet_for_copier = self._console.is_quiet
        data: dict[str, Any] = _load_yaml_data(config_file) if config_file is not None else {}
        data["repository_name"] = name
        try:
            copier.run_copy(
                template,
                target_dir,
                data=data,
                vcs_ref=version if is_github else None,
                unsafe=True,
                quiet=quiet_for_copier,
            )
        except Exception as e:
            # copier's own exceptions are inconsistent -- some are
            # copier.errors.CopierError subclasses, others (e.g. an invalid
            # local template path) are bare ValueErrors -- so every failure
            # from this call is normalized into our own exception hierarchy
            # here, rather than leaving callers to guess which of copier's
            # exception types to expect.
            raise ConfigurationError(f"Failed to render template '{template}': {e}") from e

        self._generate_certificates(target_dir)
        self._clean_docker_state(target_dir)
        self._init_git(target_dir)

        self._console.success(f"✓ Repository '{name}' created successfully.\n")
        return target_dir

    def _generate_certificates(self, target_dir: Path) -> None:
        """Generate a self-signed development TLS cert/key pair.

        Matches ``repository_installer.sh``'s ``openssl`` invocation
        exactly: same RSA key size, validity period, and subject.
        """
        docker_dir = target_dir / "docker"
        self._console.info("→ Generating development TLS certificate\n")
        process.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:4096",
                "-nodes",
                "-out",
                str(docker_dir / "development.crt"),
                "-keyout",
                str(docker_dir / "development.key"),
                "-days",
                "3650",
                "-subj",
                DEVELOPMENT_CERT_SUBJECT,
            ],
            output_mode=ProcessOutputMode.INTERACTIVE,
        )

    def _clean_docker_state(self, target_dir: Path) -> None:
        """Best-effort ``docker compose down`` for any stale containers left
        over from a previous attempt at this repository name.

        Matches ``repository_installer.sh``'s transient ``.env`` symlink
        (``ln -s ../variables .env``, used only so ``docker compose`` can
        resolve its variable substitutions, then removed again
        immediately after) -- the failure of ``docker compose down``
        itself is ignored (``|| true`` in the shell script), since a
        brand-new repository name should never have any containers to
        remove in the first place.
        """
        docker_dir = target_dir / "docker"
        env_symlink = docker_dir / ".env"
        env_symlink.symlink_to(Path("..") / "variables")
        try:
            process.run(
                ["docker", "compose", "down"],
                cwd=docker_dir,
                check=False,
                output_mode=ProcessOutputMode.INTERACTIVE,
            )
        finally:
            env_symlink.unlink()

    def _init_git(self, target_dir: Path) -> None:
        """Initialize a git repository with an initial commit.

        Skipped in CI or without git installed, matching
        ``repository_installer.sh``'s ``[[ -z "${CI:-}" ]] && command -v
        git`` check exactly -- any non-empty ``CI`` value skips this, not
        just ``CI=true``.
        """
        if os.environ.get("CI"):
            return
        if shutil.which("git") is None:
            return

        self._console.info("→ Initializing git repository\n")
        process.run(
            ["git", "init", "-b", "main"], cwd=target_dir, output_mode=ProcessOutputMode.INTERACTIVE
        )
        process.run(["git", "add", "."], cwd=target_dir, output_mode=ProcessOutputMode.INTERACTIVE)
        process.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=target_dir,
            output_mode=ProcessOutputMode.INTERACTIVE,
        )
