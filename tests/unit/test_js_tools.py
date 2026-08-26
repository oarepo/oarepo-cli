# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Unit tests for the JavaScript-test setup helpers in ``services.js_tools``.

These cover the pure/logic pieces of ``jstest --setup`` in isolation --
package.json/pnpm-workspace patching, marker parsing, entry/devDep discovery
(with the ``invenio shell`` call mocked) and the ``setup_jstests``
orchestration (with the invenio/pnpm subprocesses mocked). A real end-to-end
run needs an installed venv plus node/webpack and is out of scope here (see
``tests/integration/test_library_jstest_setup.py`` for the CLI wiring).
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from oarepo_cli.core.context import ProjectContext
from oarepo_cli.core.errors import ConfigurationError
from oarepo_cli.services import js_tools, process, repository


def _result(stdout: str = "", **overrides: object) -> process.ProcessResult:
    defaults: dict[str, object] = {
        "return_code": 0,
        "stdout": stdout,
        "stderr": "",
        "command": [],
        "cwd": Path(),
        "duration_ms": 0,
    }
    defaults.update(overrides)
    return process.ProcessResult(**defaults)  # type: ignore[arg-type]


# --- _ensure_npm_script ------------------------------------------------------


def test_ensure_npm_script_adds_when_missing(tmp_path: Path) -> None:
    package_file = tmp_path / "package.json"
    package_file.write_text(json.dumps({"name": "assets", "scripts": {"build": "webpack"}}))

    js_tools._ensure_npm_script(package_file, "test", "jest $@")

    data = json.loads(package_file.read_text())
    assert data["scripts"]["test"] == "jest $@"
    # existing content is preserved
    assert data["scripts"]["build"] == "webpack"
    assert data["name"] == "assets"


def test_ensure_npm_script_keeps_existing_definition(tmp_path: Path) -> None:
    package_file = tmp_path / "package.json"
    package_file.write_text(json.dumps({"scripts": {"test": "my-own-runner"}}))

    js_tools._ensure_npm_script(package_file, "test", "jest $@")

    assert json.loads(package_file.read_text())["scripts"]["test"] == "my-own-runner"


def test_ensure_npm_script_creates_scripts_block(tmp_path: Path) -> None:
    package_file = tmp_path / "package.json"
    package_file.write_text(json.dumps({"name": "assets"}))

    js_tools._ensure_npm_script(package_file, "test", "jest $@")

    assert json.loads(package_file.read_text())["scripts"] == {"test": "jest $@"}


# --- _patch_pnpm_workspace ---------------------------------------------------


def test_patch_pnpm_workspace_adds_packages_key(tmp_path: Path) -> None:
    workspace = tmp_path / "pnpm-workspace.yaml"
    workspace.write_text("someKey: value\n")

    js_tools._patch_pnpm_workspace(workspace)

    text = workspace.read_text()
    assert "packages: []" in text
    assert "someKey: value" in text  # existing content preserved


def test_patch_pnpm_workspace_noop_when_present(tmp_path: Path) -> None:
    workspace = tmp_path / "pnpm-workspace.yaml"
    original = "packages:\n  - a\n"
    workspace.write_text(original)

    js_tools._patch_pnpm_workspace(workspace)

    assert workspace.read_text() == original


def test_patch_pnpm_workspace_creates_when_absent(tmp_path: Path) -> None:
    workspace = tmp_path / "pnpm-workspace.yaml"

    js_tools._patch_pnpm_workspace(workspace)

    assert workspace.read_text() == "packages: []\n"


# --- _marked_result ----------------------------------------------------------


def test_marked_result_extracts_line_amid_noise() -> None:
    output = "some log line\nOAREPO_WEBPACK_ENTRIES:./js/a,./js/b\ntrailing noise\n"

    assert js_tools._marked_result(output, js_tools._ENTRIES_MARKER) == "./js/a,./js/b"


def test_marked_result_absent_returns_empty() -> None:
    assert js_tools._marked_result("no marker here\n", js_tools._ENTRIES_MARKER) == ""


# --- discovery (invenio shell mocked) ----------------------------------------


def test_get_webpack_entries_parses_and_passes_package_env(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_shell(context: object, code: str, *, env: dict[str, str] | None = None) -> process.ProcessResult:
        captured["code"] = code
        captured["env"] = env
        return _result("boot log noise\nOAREPO_WEBPACK_ENTRIES:./js/foo,./js/bar\n")

    monkeypatch.setattr("oarepo_cli.services.repository.run_invenio_shell", fake_shell)

    entries = js_tools._get_webpack_entries(Mock(spec=ProjectContext), "mypkg")

    assert entries == ["./js/foo", "./js/bar"]
    assert captured["env"] == {"OAREPO_WEBPACK_PACKAGE": "mypkg"}
    # the real webpack_entries.py script is what gets executed
    assert "invenio_assets.webpack" in captured["code"]  # type: ignore[operator]


def test_get_webpack_entries_empty_when_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "oarepo_cli.services.repository.run_invenio_shell",
        lambda *_a, **_k: _result("OAREPO_WEBPACK_ENTRIES:\n"),
    )

    assert js_tools._get_webpack_entries(Mock(spec=ProjectContext), "mypkg") == []


def test_get_rdm_dev_deps_parses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "oarepo_cli.services.repository.run_invenio_shell",
        lambda *_a, **_k: _result("noise\nOAREPO_RDM_DEV_DEPS:jest@^29 babel-jest@^29\n"),
    )

    assert js_tools._get_rdm_dev_deps(Mock(spec=ProjectContext)) == ["jest@^29", "babel-jest@^29"]


# --- repository.run_invenio_shell primitive ----------------------------------


def test_run_invenio_shell_builds_command_and_captures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(cmd: list[str], **kwargs: object) -> process.ProcessResult:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _result("hello")

    monkeypatch.setattr("oarepo_cli.services.repository.process.run", fake_run)
    monkeypatch.setattr("oarepo_cli.services.repository.get_invenio_binary", lambda _c: Path("/venv/bin/invenio"))
    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path

    result = repository.run_invenio_shell(context, "print(1)", env={"A": "b"})

    assert captured["cmd"] == ["/venv/bin/invenio", "shell", "-c", "print(1)"]
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["env"] == {"A": "b"}
    assert kwargs["check"] is True
    assert result.stdout == "hello"


# --- setup_jstests orchestration (subprocesses mocked) -----------------------


def test_setup_jstests_writes_config_and_installs_deps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "package.json").write_text("{}")
    (assets / "pnpm-workspace.yaml").write_text("")

    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.pyproject_path = tmp_path / "pyproject.toml"

    invenio_calls: list[list[str]] = []
    monkeypatch.setattr("oarepo_cli.services.repository.get_instance_path", lambda _c: tmp_path)
    monkeypatch.setattr(
        "oarepo_cli.services.repository._run_invenio",
        lambda _c, args, **_k: invenio_calls.append(list(args)),
    )
    monkeypatch.setattr(
        "oarepo_cli.services.pyproject_reader.PyProjectReader.read",
        lambda _self, _p: SimpleNamespace(name="mypkg"),
    )
    monkeypatch.setattr(js_tools, "_get_webpack_entries", lambda _c, _pkg: ["./js/foo"])
    monkeypatch.setattr(js_tools, "_get_rdm_dev_deps", lambda _c: ["jest@^29"])

    pnpm_calls: list[list[str]] = []
    monkeypatch.setattr(
        "oarepo_cli.services.js_tools.process.run",
        lambda cmd, **_k: pnpm_calls.append(list(cmd)) or _result(),
    )

    result = js_tools.setup_jstests(context, quiet=True)

    assert result.return_code == 0
    # webpack project created + assets collected/installed
    assert ["webpack", "clean", "create"] in invenio_calls
    assert ["collect"] in invenio_calls
    assert ["webpack", "install"] in invenio_calls
    # jest config generated with the computed coverage glob for our entry
    jest_config = (assets / "jest.config.js").read_text()
    assert '"**/js/foo/**/*.{js,jsx}"' in jest_config
    assert (assets / "setupTests.js").exists()
    # the `test` npm script was wired in
    assert json.loads((assets / "package.json").read_text())["scripts"]["test"] == "jest"
    # pnpm installed the RDM dev dependency
    assert any("pnpm" in call and "jest@^29" in call for call in pnpm_calls)
    # the assets path is substituted in POSIX form (forward slashes)
    assert assets.as_posix() in jest_config


def test_setup_jstests_fails_without_webpack_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No webpack entry points -> actionable error, and no jest.config.js written."""
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "package.json").write_text("{}")
    (assets / "pnpm-workspace.yaml").write_text("")

    context = Mock(spec=ProjectContext)
    context.root_directory = tmp_path
    context.pyproject_path = tmp_path / "pyproject.toml"

    monkeypatch.setattr("oarepo_cli.services.repository.get_instance_path", lambda _c: tmp_path)
    monkeypatch.setattr("oarepo_cli.services.repository._run_invenio", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "oarepo_cli.services.pyproject_reader.PyProjectReader.read",
        lambda _self, _p: SimpleNamespace(name="mypkg"),
    )
    monkeypatch.setattr(js_tools, "_get_webpack_entries", lambda _c, _pkg: [])

    with pytest.raises(ConfigurationError, match=r"invenio_assets\.webpack"):
        js_tools.setup_jstests(context, quiet=True)

    # bailed out before writing a syntactically-broken config
    assert not (assets / "jest.config.js").exists()
