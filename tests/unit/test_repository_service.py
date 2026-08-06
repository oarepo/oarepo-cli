# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for repository service module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from oarepo_cli.core.config import CliConfig, SecurityConfig
from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.platform import get_platform_detector
from oarepo_cli.services import process, repository


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
    invenio_private.write_text("# Existing config\nsearch_port = 1234\nsome_other_setting = 'value'\n")

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


def test_get_instance_path_defaults_to_venv_var_instance(mock_context: Mock, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without INVENIO_INSTANCE_PATH, it's <venv>/var/instance (Invenio's own default)."""
    monkeypatch.delenv("INVENIO_INSTANCE_PATH", raising=False)
    mock_context.venv_path = Path("/fake/project/.venv")

    result = repository.get_instance_path(mock_context)

    assert result == Path("/fake/project/.venv/var/instance")


def test_get_instance_path_honors_invenio_instance_path_env(
    mock_context: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """INVENIO_INSTANCE_PATH, when set, overrides the venv-derived default."""
    monkeypatch.setenv("INVENIO_INSTANCE_PATH", "/custom/instance/path")
    mock_context.venv_path = Path("/fake/project/.venv")

    result = repository.get_instance_path(mock_context)

    assert result == Path("/custom/instance/path")


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


def _fake_process_result(**overrides: object) -> process.ProcessResult:
    defaults: dict[str, object] = {
        "return_code": 0,
        "stdout": "",
        "stderr": "",
        "command": [],
        "cwd": Path(),
        "duration_ms": 0,
    }
    defaults.update(overrides)
    return process.ProcessResult(**defaults)  # type: ignore[arg-type]


def test_upgrade_repository_cleans_cache_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Upgrade repository runs uv cache clean --force by default.

    Runs when clean_cache is left at its default (True). Matches
    `repository upgrade`'s bash-compatible behavior.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"
    context.config = CliConfig()

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> process.ProcessResult:
        calls.append(list(command))
        return _fake_process_result()

    monkeypatch.setattr("oarepo_cli.services.repository.process.run", fake_run)
    monkeypatch.setattr("oarepo_cli.services.repository.VirtualEnvironmentManager.cleanup", lambda _self: None)
    monkeypatch.setattr("oarepo_cli.services.repository.install_repository", lambda *_args, **_kwargs: None)

    repository.upgrade_repository(context, quiet=True)

    assert ["uv", "cache", "clean", "--force"] in calls


def test_upgrade_repository_skips_cache_clean_when_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Upgrade repository with clean_cache=False skips cache cleaning.

    Used by LocalPackageManager -- never runs `uv cache clean`, since
    adding/removing a local package doesn't change any other package's version
    and purging the cache would just force a wasted re-download.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"
    context.config = CliConfig()

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> process.ProcessResult:
        calls.append(list(command))
        return _fake_process_result()

    monkeypatch.setattr("oarepo_cli.services.repository.process.run", fake_run)
    monkeypatch.setattr("oarepo_cli.services.repository.VirtualEnvironmentManager.cleanup", lambda _self: None)
    install_calls: list[object] = []
    monkeypatch.setattr(
        "oarepo_cli.services.repository.install_repository",
        lambda *_args, **kwargs: install_calls.append(kwargs),
    )

    repository.upgrade_repository(context, quiet=True, clean_cache=False)

    assert calls == []
    assert install_calls == [{"quiet": True}]


def test_get_invenio_binary_resolves_venv_bin_dir(tmp_path: Path) -> None:
    """Get invenio binary resolves venv/bin_dir/invenio.

    Platform-aware.
    """
    context = Mock(spec=ProjectContext)
    context.venv_path = tmp_path / ".venv"

    bin_dir = get_platform_detector().get_venv_bin_dir()
    assert repository.get_invenio_binary(context) == tmp_path / ".venv" / bin_dir / "invenio"


def test_exec_invenio_chdirs_and_execs_resolved_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exec invenio chdirs into the project root first.

    Execve has no cwd of its own, then execve's into the venv's own invenio
    binary with args appended, setting PYTHONWARNINGS=ignore like
    repository_runner.sh's run_invenio().
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"

    chdir_calls = []
    execve_calls = []
    monkeypatch.setattr("oarepo_cli.services.repository.os.chdir", chdir_calls.append)
    monkeypatch.setattr(
        "oarepo_cli.services.repository.os.execve",
        lambda *args: execve_calls.append(args),
    )

    repository.exec_invenio(context, ["db", "upgrade"])

    assert chdir_calls == [tmp_path]
    assert len(execve_calls) == 1
    binary, argv, env = execve_calls[0]
    expected_binary = str(repository.get_invenio_binary(context))
    assert binary == expected_binary
    assert argv == [expected_binary, "db", "upgrade"]
    assert env["PYTHONWARNINGS"] == "ignore"


def test_exec_invenio_and_exec_shell_apply_same_env_defaults_as_blocking_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exec invenio and exec shell apply same env defaults as blocking calls.

    Their environments get the same OAREPO_ENV_DEFAULTS/venv-stripping
    treatment any process.run() call gets, rather than building their env from
    bare os.environ, which would silently miss both.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"

    monkeypatch.setenv("VIRTUAL_ENV", "/oarepo-cli/own/venv")
    monkeypatch.delenv("INVENIO_APP_THEME", raising=False)
    monkeypatch.setattr("oarepo_cli.services.repository.os.chdir", lambda _path: None)

    invenio_execve_calls = []
    monkeypatch.setattr(
        "oarepo_cli.services.repository.os.execve",
        lambda *args: invenio_execve_calls.append(args),
    )
    repository.exec_invenio(context, ["db", "upgrade"])
    _binary, _argv, invenio_env = invenio_execve_calls[0]
    assert invenio_env["INVENIO_APP_THEME"] == '["semantic-ui"]'

    shell_execve_calls = []
    monkeypatch.setattr(
        "oarepo_cli.services.repository.os.execve",
        lambda *args: shell_execve_calls.append(args),
    )
    repository.exec_shell(context)
    _bash_path, _argv, shell_env = shell_execve_calls[0]
    # exec_shell() explicitly overrides VIRTUAL_ENV to the *target* venv -- that's not
    # the same as failing to strip oarepo-cli's own -- but the default it should have
    # picked up (independent of anything exec_shell sets explicitly) proves the
    # underlying env was actually built via build_subprocess_env(), not bare os.environ.
    assert shell_env["INVENIO_APP_THEME"] == '["semantic-ui"]'


def test_exec_shell_sets_up_venv_activation_and_execs_bash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Exec shell sets up venv activation and execs bash.

    Chdirs into the project root, activates the venv (VIRTUAL_ENV/PATH,
    VIRTUAL_ENV_PROMPT, a fallback PS1), and execve's into the default shell
    -- without loading any .env-services variables, unlike library_shell.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"

    monkeypatch.delenv("VIRTUAL_ENV_DISABLE_PROMPT", raising=False)
    monkeypatch.setenv("PROMPT_COMMAND", "some_prompt_tool")

    chdir_calls = []
    execve_calls = []
    monkeypatch.setattr("oarepo_cli.services.repository.os.chdir", chdir_calls.append)
    monkeypatch.setattr(
        "oarepo_cli.services.repository.os.execve",
        lambda *args: execve_calls.append(args),
    )

    repository.exec_shell(context)

    assert chdir_calls == [tmp_path]
    assert len(execve_calls) == 1
    bash_path, argv, env = execve_calls[0]
    bin_dir = get_platform_detector().get_venv_bin_dir()
    assert bash_path == get_platform_detector().get_default_shell()
    assert argv == ["bash"]
    assert env["VIRTUAL_ENV"] == str(context.venv_path)
    assert env["PATH"].startswith(str(context.venv_path / bin_dir))
    assert env["VIRTUAL_ENV_PROMPT"] == tmp_path.name
    assert env["PS1"] == f"({tmp_path.name}) \\u@\\h:\\w\\$ "
    assert "PROMPT_COMMAND" not in env
    assert env["BASH_SILENCE_DEPRECATION_WARNING"] == "1"


def test_rebuild_index_runs_expected_invenio_sequence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Rebuild index runs the expected invenio subcommand sequence.

    Runs the exact invenio subcommand sequence repository_runner.sh's
    rebuild_index() does, via the bare venv invenio binary.
    """
    context = Mock(spec=ProjectContext)
    context.venv_path = tmp_path / ".venv"
    context.root_directory = tmp_path

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> process.ProcessResult:
        calls.append(list(command))
        return _fake_process_result()

    monkeypatch.setattr("oarepo_cli.services.repository.process.run", fake_run)

    repository.rebuild_index(context, quiet=True)

    invenio = str(repository.get_invenio_binary(context))
    assert calls == [
        [invenio, "index", "destroy", "--yes-i-know"],
        [invenio, "index", "init"],
        [invenio, "rdm-records", "custom-fields", "init"],
        [invenio, "communities", "custom-fields", "init"],
        [invenio, "rdm", "rebuild-all-indices"],
    ]


def test_reset_repository_runs_expected_sequence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset repository runs the expected sequence.

    Destroys services (ignoring failure), wipes venv/lock/private config,
    cleans the uv cache, reinstalls, sets up services, and seeds a demo admin.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"
    context.config = CliConfig(
        security=SecurityConfig(demo_user_password="testpass123"),  # noqa: S106 - just a test password
    )

    invenio_cli_calls: list[dict[str, object]] = []
    process_calls: list[list[str]] = []
    install_calls: list[object] = []
    cleanup_calls: list[object] = []

    def fake_run_invenio_cli(_context: object, args: list[str], **kwargs: object) -> None:
        invenio_cli_calls.append({"args": list(args), **kwargs})

    def fake_process_run(command: list[str], **_kwargs: object) -> process.ProcessResult:
        process_calls.append(list(command))
        return _fake_process_result()

    monkeypatch.setattr("oarepo_cli.services.repository.invenio_cli.run_invenio_cli", fake_run_invenio_cli)
    monkeypatch.setattr("oarepo_cli.services.repository.process.run", fake_process_run)
    monkeypatch.setattr(
        "oarepo_cli.services.repository.install_repository",
        lambda _context, **kwargs: install_calls.append(kwargs),
    )
    monkeypatch.setattr(
        "oarepo_cli.services.repository.VirtualEnvironmentManager.cleanup",
        lambda _self: cleanup_calls.append(True),
    )

    (tmp_path / "uv.lock").write_text("old lock")
    (tmp_path / ".invenio.private").write_text("old settings")

    repository.reset_repository(context, quiet=True)

    # services destroy runs with check=False (failure ignored, like `services destroy || true`)
    assert invenio_cli_calls[0]["args"] == ["services", "destroy"]
    assert invenio_cli_calls[0]["check"] is False

    assert cleanup_calls == [True]
    assert not (tmp_path / "uv.lock").exists()
    assert not (tmp_path / ".invenio.private").exists()
    assert ["uv", "cache", "clean", "--force"] in process_calls

    assert install_calls == [{"quiet": True}]

    # services setup -N runs with check=True (must succeed, aborts reset otherwise)
    assert invenio_cli_calls[1]["args"] == ["services", "setup", "-N"]
    assert invenio_cli_calls[1]["check"] is True

    invenio = str(repository.get_invenio_binary(context))
    assert [invenio, "roles", "create", "administration"] in process_calls
    assert [
        invenio,
        "access",
        "allow",
        "administration-access",
        "role",
        "administration",
    ] in process_calls
    assert [
        invenio,
        "users",
        "create",
        "-a",
        "-c",
        "user@demo.org",
        "--password",
        "testpass123",
    ] in process_calls
    assert [invenio, "roles", "add", "user@demo.org", "administration"] in process_calls


def test_list_repository_models_finds_valid_models(tmp_path: Path) -> None:
    """List repository models finds valid models.

    Only counts dirs with both .copier-answers.yml and model.py, extracting
    the version from the first `version = "..."` match.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    valid = tmp_path / "models" / "valid_model"
    valid.mkdir(parents=True)
    (valid / ".copier-answers.yml").write_text("_src_path: x\n")
    (valid / "model.py").write_text('METADATA = {}\nversion = "1.2.3"\n')

    no_version = tmp_path / "models" / "no_version_model"
    no_version.mkdir(parents=True)
    (no_version / ".copier-answers.yml").write_text("_src_path: x\n")
    (no_version / "model.py").write_text("METADATA = {}\n")

    missing_answers = tmp_path / "models" / "missing_answers"
    missing_answers.mkdir(parents=True)
    (missing_answers / "model.py").write_text('version = "9.9.9"\n')

    not_a_model_dir = tmp_path / "models" / "just_a_dir"
    not_a_model_dir.mkdir(parents=True)

    models = repository.list_repository_models(context)

    # missing_answers (no .copier-answers.yml) and just_a_dir (neither file) are excluded;
    # remaining two are sorted by directory name.
    assert models == [
        repository.ModelInfo(name="no_version_model", version="unknown"),
        repository.ModelInfo(name="valid_model", version="1.2.3"),
    ]


def test_list_repository_models_returns_empty_without_models_dir(tmp_path: Path) -> None:
    """List repository models returns empty without models directory.

    No models/ directory at all results in empty list, not an error.
    """
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    assert repository.list_repository_models(context) == []


def test_get_python_version_returns_stripped_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Get python version returns stripped output.

    Runs `<python_binary> --version` and returns the stripped output,
    mirroring repository_runner.sh's show_info()'s `"$PYTHON" --version`.
    """
    context = Mock(spec=ProjectContext)
    context.python_binary = Path("/usr/bin/python3.14")

    monkeypatch.setattr(
        "oarepo_cli.services.repository.process.run",
        lambda *_args, **_kwargs: _fake_process_result(stdout="Python 3.14.4\n"),
    )

    assert repository.get_python_version(context) == "Python 3.14.4"


def _run_tests_context(tmp_path: Path, *, code_directories: list[Path]) -> Mock:
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.venv_path = tmp_path / ".venv"
    # Deliberately distinct from the venv's own python (a system/version-resolver
    # interpreter, used only to *create* the venv) -- installing into it directly, as
    # opposed to the venv's own python, would fail against a uv-managed interpreter
    # ("externally managed", found the hard way against a real fixture).
    context.python_binary = Path("/usr/bin/python3.14")
    context.code_directories = code_directories
    return context


def _mock_exec(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, ...]]:
    """Mock os.chdir/os.execve at the repository module.

    So run_tests() never really exec's (which would replace the test runner's
    own process).
    """
    execve_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr("oarepo_cli.services.repository.os.chdir", lambda _path: None)
    monkeypatch.setattr(
        "oarepo_cli.services.repository.os.execve",
        lambda *args: execve_calls.append(args),
    )
    return execve_calls


def test_run_tests_installs_pytest_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run tests installs pytest when missing.

    Installs pytest into the venv's own python directly (not via a "tests"
    extras group, unlike TestOrchestrator, and not context.python_binary,
    which is the interpreter used to *create* the venv, not the venv's own)
    when it isn't already there. A fresh repository has no "tests" extras
    convention to rely on.
    """
    context = _run_tests_context(tmp_path, code_directories=[])
    bin_dir = get_platform_detector().get_venv_bin_dir()
    venv_python = context.venv_path / bin_dir / "python"

    calls: list[list[str]] = []

    def fake_run(command: list[str], **_kwargs: object) -> process.ProcessResult:
        calls.append(list(command))
        return _fake_process_result()

    monkeypatch.setattr("oarepo_cli.services.repository.process.run", fake_run)
    _mock_exec(monkeypatch)

    repository.run_tests(context, quiet=True)

    install_call = next(c for c in calls if c[:3] == ["uv", "pip", "install"])
    assert install_call[-1] == "pytest"
    assert str(venv_python) in install_call
    assert str(context.python_binary) not in install_call


def test_run_tests_skips_pytest_install_when_already_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run tests skips pytest install when already present.

    Doesn't reinstall pytest if the venv's own binary already exists.
    """
    context = _run_tests_context(tmp_path, code_directories=[])
    bin_dir = get_platform_detector().get_venv_bin_dir()
    pytest_bin = context.venv_path / bin_dir / "pytest"
    pytest_bin.parent.mkdir(parents=True)
    pytest_bin.touch()

    calls: list[list[str]] = []
    monkeypatch.setattr(
        "oarepo_cli.services.repository.process.run",
        lambda command, **_kwargs: calls.append(list(command)) or _fake_process_result(),
    )
    _mock_exec(monkeypatch)

    repository.run_tests(context, quiet=True)

    assert not any(c[:3] == ["uv", "pip", "install"] for c in calls)


def test_run_tests_execs_pytest_with_correct_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Run tests execs pytest with correct environment.

    Chdirs into the project root (execve has no cwd of its own) and execve's
    into the venv's own pytest, rather than blocking on a subprocess --
    there's nothing to do afterward (no services to stop, unlike library test),
    so a terminal Ctrl+C hits pytest directly and its exit code is preserved
    exactly.
    """
    context = _run_tests_context(tmp_path, code_directories=[])
    bin_dir = get_platform_detector().get_venv_bin_dir()
    pytest_bin = context.venv_path / bin_dir / "pytest"
    pytest_bin.parent.mkdir(parents=True)
    pytest_bin.touch()
    monkeypatch.setattr("oarepo_cli.services.repository.process.run", lambda *a, **k: None)  # noqa: ARG005
    chdir_calls = []
    execve_calls = []
    monkeypatch.setattr("oarepo_cli.services.repository.os.chdir", chdir_calls.append)
    monkeypatch.setattr(
        "oarepo_cli.services.repository.os.execve",
        lambda *args: execve_calls.append(args),
    )

    repository.run_tests(context, quiet=True)

    assert chdir_calls == [tmp_path]
    assert len(execve_calls) == 1
    binary, argv, env = execve_calls[0]
    assert binary == str(pytest_bin)
    assert argv == [str(pytest_bin)]
    assert env["PATH"]  # a real, built environment, not an empty dict


def test_run_tests_covers_every_module_directory_not_a_single_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run tests covers every module directory with coverage.

    With --with-coverage covers every non-tests code_directories entry by
    name -- unlike TestOrchestrator's single [project].name-derived target,
    since a repository's code_directories are typically several real,
    importable top-level packages, not one src/-or-package-dir.
    """
    common = tmp_path / "common"
    i18n = tmp_path / "i18n"
    tests_dir = tmp_path / "tests"
    context = _run_tests_context(tmp_path, code_directories=[common, i18n, tests_dir])
    bin_dir = get_platform_detector().get_venv_bin_dir()
    pytest_bin = context.venv_path / bin_dir / "pytest"
    pytest_bin.parent.mkdir(parents=True)
    pytest_bin.touch()
    (context.venv_path / bin_dir / "python").touch()

    monkeypatch.setattr(
        "oarepo_cli.services.repository.process.run",
        lambda *_a, **_k: _fake_process_result(),
    )
    execve_calls = _mock_exec(monkeypatch)

    repository.run_tests(context, coverage=True, quiet=True)

    _binary, argv, _env = execve_calls[0]
    assert argv.count("--cov") == 2
    assert "common" in argv
    assert "i18n" in argv
    assert "tests" not in argv


def test_run_tests_forwards_pytest_args(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Extra pytest args are appended verbatim to the pytest invocation."""
    context = _run_tests_context(tmp_path, code_directories=[])
    bin_dir = get_platform_detector().get_venv_bin_dir()
    pytest_bin = context.venv_path / bin_dir / "pytest"
    pytest_bin.parent.mkdir(parents=True)
    pytest_bin.touch()

    execve_calls = _mock_exec(monkeypatch)

    repository.run_tests(context, pytest_args=["-v", "-k", "test_specific"], quiet=True)

    _binary, argv, _env = execve_calls[0]
    assert argv[-3:] == ["-v", "-k", "test_specific"]
