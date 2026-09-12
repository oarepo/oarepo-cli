# SPDX-FileCopyrightText: 2026 CESNET z.s.p.o.
# SPDX-License-Identifier: MIT

"""Startup bootstrap for the not-yet-released RustFS-capable docker-services-cli.

Why this exists
---------------
``oarepo-cli`` needs a ``docker-services-cli`` build that knows about RustFS. No
published release has it yet, so ``pyproject.toml`` pins a fork through
``[tool.uv.sources]``. uv only honours ``[tool.uv.sources]`` for the *root*
project of a resolution though: a project that merely *depends* on
``oarepo-cli`` resolves ``docker-services-cli`` from PyPI and ends up with a
build without RustFS support. No dependency declaration can propagate a git
source through a library, so this bootstrap repairs the environment instead.

How this works
--------------
``pyproject.toml`` force-includes the bundled ``oarepo_cli_rustfs_bootstrap.pth``
and this module at site-packages *root* -- this file lives in the package for the
sake of linting and tests, but ships as ``_oarepo_cli_docker_services_cli_patch.py``
next to it. CPython's ``site`` module executes the ``.pth`` line while the
interpreter is still starting up, i.e. before any user code runs and therefore
before anything can import ``docker_services_cli``.
``bootstrap()`` checks whether the installed distribution really came from the
fork's ``rustfs`` branch -- through the PEP 610 ``direct_url.json`` file, since
the version number alone cannot tell the two builds apart -- and runs
``uv pip install --python <this interpreter>`` for the git build when it did not.
The install replaces the package in place; the import caches are then
invalidated and any ``docker_services_cli`` entry in ``sys.modules`` dropped, so
the rest of the interpreter's life only ever sees the freshly installed build.

Constraints (why this module looks the way it does)
---------------------------------------------------
- *stdlib only*, and in particular it must never import from ``oarepo_cli``: it
  runs while ``site`` is still initialising, possibly in the middle of an install
  transaction where other distributions are not importable yet. Importing the
  package would pull in typer/rich and fail. Being inside the package tree is a
  source-tree arrangement only; at runtime this is a top-level module.
- *never raises*: a broken bootstrap must degrade to "keep the currently
  installed build". ``services.services_lifecycle`` then fails fast with an
  actionable message instead of this hook having broken the interpreter.
- *cheap and idempotent*: it runs on every interpreter start in the environment,
  including short-lived subprocesses, so the happy path is a single metadata
  read. Note that one interpreter can execute the ``.pth`` line more than once,
  which the module-level guard below absorbs.
- *non-recursive and non-colliding*: concurrent startups serialise on a lock
  file. This bootstrap's own installer subprocess (and anything it spawns) is
  suppressed via an inherited env var, ``_RECURSION_GUARD_ENV_VAR`` -- needed
  because pip's build-isolation and PEP 517 hook subprocesses don't look like
  "pip" in argv and so can't be caught by argv-sniffing. A *user- or CI-driven*
  pip install of this same environment, which this bootstrap never started and
  so never handed that env var to, is instead caught by ``_running_under_pip()``
  reading ``sys.orig_argv``. Neither guard can stand in for the other.

Removing this workaround means deleting this module and the bundled ``.pth``
hook, their ``[tool.hatch.build.targets.wheel.force-include]`` entries, the
``[tool.uv.sources]`` entry and the ``docker-services-cli`` comments in
``pyproject.toml`` -- possible once RustFS support ships in a real
``docker-services-cli`` release.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from collections.abc import Mapping
from importlib import metadata
from pathlib import Path

# Keep these in sync with the docker-services-cli dependency and its
# [tool.uv.sources] entry in pyproject.toml.
PACKAGE_NAME = "docker-services-cli"
GIT_REPOSITORY_URL = "https://github.com/mesemus/docker-services-cli"
GIT_REVISION = "rustfs"

#: PEP 508 direct reference for the fork's branch, asked for with the same extra
#: as the dependency declaration in pyproject.toml.
INSTALL_REQUIREMENT = f"{PACKAGE_NAME}[s3] @ git+{GIT_REPOSITORY_URL}@{GIT_REVISION}"

#: Import name of the package this bootstrap keeps current (not of this module).
PATCHED_MODULE = "docker_services_cli"

#: Set to any value to leave the environment alone (air-gapped runs, debugging).
SKIP_ENV_VAR = "OAREPO_SKIP_DOCKER_SERVICES_PATCH"
#: Set to any value to re-run the install even when the branch already matches,
#: i.e. to move to the current head of the branch instead of a stale commit.
#: Cleared once the install succeeded so subprocesses don't repeat it.
FORCE_ENV_VAR = "OAREPO_FORCE_DOCKER_SERVICES_PATCH"
#: Set on the installer subprocess's own environment so any interpreter it
#: starts skips too -- including pip's build-isolation installer and PEP 517
#: hook runners, which look nothing like "pip" in argv and so are invisible
#: to ``_running_under_pip()``. Reaches them purely through env inheritance.
_RECURSION_GUARD_ENV_VAR = "OAREPO_CLI_DOCKER_SERVICES_PATCH_RUNNING"

#: Matches the basename of pip's own entry-point scripts (``pip``, ``pip3``,
#: ``pip3.14``, ...), but not unrelated scripts that merely start with "pip"
#: (``pipx``, ``pipeline.py``, ``pip_audit``, ...).
_PIP_ENTRY_POINT_RE = re.compile(r"pip(\d+(\.\d+)?)?$")

STATE_DIR_NAME = ".oarepo-cli-docker-services-cli-patch"
LOCK_FILE_NAME = "install.lock"
FAILURE_FILE_NAME = "last-failure"

#: The git build has to be cloned and built, so allow for a slow first run.
INSTALL_TIMEOUT_SECONDS = 300.0
#: How long to let another process finish the same install before giving up.
#: Deliberately short: this runs during interpreter startup, and the process
#: holding the lock can even be one this bootstrap itself started, so waiting
#: long here could stall the very install being waited for. A startup hook must
#: not block; losing one run is cheap (the next interpreter start retries).
LOCK_TIMEOUT_SECONDS = 15.0
#: A lock older than this is treated as left over from a dead process.
LOCK_STALE_SECONDS = 900.0
#: Don't retry a failed install (typically: no network) on every interpreter start.
FAILURE_COOLDOWN_SECONDS = 900.0

# One interpreter can execute the .pth line more than once per startup, and doing
# the whole bootstrap twice in one process is at best a waste of time.
_bootstrapped = False


def _repository_key(url: str) -> str:
    """Reduce a VCS URL to a comparable ``host/path`` identity.

    ``direct_url.json`` records the URL in whatever spelling it was installed
    from (``git+https://``, ``.../.git``, uv versus pip), so the recorded and the
    configured URL are both flattened before being compared.

    Args:
        url: A VCS URL, with or without a ``git+`` transport prefix.

    Returns:
        Lower-cased ``host/path`` without transport prefix or ``.git`` suffix.

    """
    url = url.strip().removeprefix("git+")
    parsed = urllib.parse.urlsplit(url)
    if parsed.netloc:
        host = parsed.netloc.rsplit("@", 1)[-1].lower()
        path = parsed.path
    else:
        # scp-like syntax without a scheme, e.g. ``git@github.com:mesemus/x.git``
        host, _, path = url.partition(":")
        host = host.rsplit("@", 1)[-1].lower()
    path = path.strip("/").removesuffix(".git").strip("/")
    return f"{host}/{path.lower()}" if path else host


def is_rustfs_build(direct_url: Mapping[str, object] | None) -> bool:
    """Tell whether a PEP 610 ``direct_url.json`` payload is the RustFS fork.

    Args:
        direct_url: Parsed ``direct_url.json`` of an installed distribution, or
            ``None`` when the distribution has none (registry installs).

    Returns:
        True if the payload points at the configured repository and branch.

    """
    if not direct_url:
        return False
    recorded_url = direct_url.get("url")
    if not isinstance(recorded_url, str) or _repository_key(recorded_url) != _repository_key(GIT_REPOSITORY_URL):
        return False
    vcs_info = direct_url.get("vcs_info")
    if not isinstance(vcs_info, Mapping):
        return False
    return str(vcs_info.get("requested_revision", "")) == GIT_REVISION


def _installed_direct_url() -> dict[str, object] | None:
    """Read the installed docker-services-cli's ``direct_url.json``, if any."""
    try:
        distribution = metadata.distribution(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None
    raw = distribution.read_text("direct_url.json")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _installed_is_rustfs_build() -> bool:
    """Tell whether the docker-services-cli installed here supports RustFS."""
    return is_rustfs_build(_installed_direct_url())


def _needs_patch() -> bool:
    """Tell whether the environment has to be repaired (checked before installing)."""
    if os.environ.get(FORCE_ENV_VAR):
        return True
    return not _installed_is_rustfs_build()


def _running_under_pip() -> bool:
    """Tell whether this interpreter's own invocation is pip itself.

    Guards against racing a *user- or CI-driven* ``pip install`` in this same
    environment: two installers touching site-packages at once can corrupt
    each other's metadata. Uses ``sys.orig_argv`` (3.10+), not ``sys.argv``:
    a ``.pth`` hook runs before ``runpy`` resolves ``-m``, so at this point
    ``python -m pip ...`` already shows up as ``sys.argv == ['-m', ...]`` --
    "pip" itself was consumed by the interpreter and never lands in argv.
    ``sys.orig_argv`` keeps the real command line instead.

    Only recognises pip's own top-level invocation (``python -m pip`` or the
    ``pip``/``pip3``/``pip3.14`` scripts) -- not the build-isolation installer
    or PEP 517 hook runners pip spawns while building a package from source
    (their argv is a path into pip's vendored internals, nothing stable to
    match). Those are instead caught by ``_RECURSION_GUARD_ENV_VAR``, but only
    when *this* bootstrap started the pip run; an unrelated pip invocation's
    build subprocesses are not covered by either guard.
    """
    orig_argv = getattr(sys, "orig_argv", None)
    args = orig_argv[1:] if orig_argv else []
    if not args:
        return False
    if args[0] == "-m":
        return args[1:2] == ["pip"]
    return _PIP_ENTRY_POINT_RE.fullmatch(Path(args[0]).name) is not None


def _pip_available() -> bool:
    """Tell whether this environment can run ``python -m pip``.

    Uses ``find_spec`` rather than ``import_module``: this runs during
    interpreter startup and importing pip just to ask a question would cost
    more than the rest of the bootstrap put together.
    """
    return importlib.util.find_spec("pip") is not None


def _install_commands() -> list[list[str]]:
    """Build the installer command(s), or an empty list when none is available.

    ``uv`` comes first: it owns the environments oarepo-cli projects use, and
    uv-created venvs usually have no pip in them. Plain ``pip`` covers
    environments set up by other means. The two don't share flags or semantics:

    - uv can pin the replacement to one package (``--upgrade-package``) and does
      replace a registry build with the same version number.
    - pip has no such flag and treats "version 0.12.3 already installed" as
      satisfied even for a different source, so it needs ``--force-reinstall``.
      With ``--no-deps``, so that the replacement doesn't churn unrelated
      packages the target project pinned; a second run then resolves just the
      dependencies the registry build never needed (the ``[s3]`` extra).

    Returns:
        Commands to run in order.

    """
    uv = shutil.which("uv")
    if uv:
        return [
            [
                uv,
                "pip",
                "install",
                "--python",
                sys.executable,
                "--upgrade-package",
                PACKAGE_NAME,
                INSTALL_REQUIREMENT,
            ]
        ]
    if _pip_available():
        return [
            [sys.executable, "-m", "pip", "install", "--force-reinstall", "--no-deps", INSTALL_REQUIREMENT],
            [sys.executable, "-m", "pip", "install", INSTALL_REQUIREMENT],
        ]
    return []


def _state_dir() -> Path:
    """Directory holding this environment's lock and cooldown bookkeeping."""
    return Path(sys.prefix) / STATE_DIR_NAME


def _in_cooldown(state_dir: Path) -> bool:
    """Tell whether a recent install failure should suppress another attempt."""
    try:
        last_failure = float((state_dir / FAILURE_FILE_NAME).read_text(encoding="utf-8").strip())
    except OSError, ValueError:
        return False
    return (time.time() - last_failure) < FAILURE_COOLDOWN_SECONDS


def _enter_cooldown(state_dir: Path) -> None:
    """Record that an install attempt failed, so it isn't retried immediately."""
    with contextlib.suppress(OSError):
        (state_dir / FAILURE_FILE_NAME).write_text(str(time.time()), encoding="utf-8")


def _leave_cooldown(state_dir: Path) -> None:
    """Forget a previous failure now that an install succeeded."""
    with contextlib.suppress(OSError):
        (state_dir / FAILURE_FILE_NAME).unlink()


def _lock_is_stale(lock: Path) -> bool:
    """Tell whether a lock file is old enough to belong to a dead process."""
    try:
        return (time.time() - lock.stat().st_mtime) > LOCK_STALE_SECONDS
    except OSError:
        return False


def _acquire_lock(lock: Path) -> bool:
    """Take the install lock, waiting for another process to finish if needed.

    Returns:
        True if the caller holds the lock and should install, False if the lock
        stayed taken (another process is installing, or has just finished).

    """
    deadline = time.monotonic() + LOCK_TIMEOUT_SECONDS
    while True:
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _installed_is_rustfs_build():
                return False
            if _lock_is_stale(lock):
                with contextlib.suppress(OSError):
                    lock.unlink()
                continue
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.1)
            continue
        except OSError:
            return False
        os.close(descriptor)
        return True


def _release_lock(lock: Path) -> None:
    """Give up the install lock."""
    with contextlib.suppress(OSError):
        lock.unlink()


def _adopt_installed_build() -> None:
    """Make the installed build the one this interpreter will import.

    Nothing imports ``docker_services_cli`` before this bootstrap runs (it runs
    during interpreter startup), but dropping stale module state and the import
    caches means a later import reads the files the installer wrote rather than
    directory listings taken before it did.
    """
    for name in [name for name in sys.modules if name == PATCHED_MODULE or name.startswith(f"{PATCHED_MODULE}.")]:
        del sys.modules[name]
    importlib.invalidate_caches()


def _install(state_dir: Path) -> None:
    """Replace the installed docker-services-cli with the fork's RustFS build."""
    commands = _install_commands()
    if not commands:
        _enter_cooldown(state_dir)
        _notify(
            f"could not update {PACKAGE_NAME} to the RustFS-capable build: neither uv nor pip is available "
            f"in this environment. Install it manually: {INSTALL_REQUIREMENT}"
        )
        return

    _notify(f"installing the RustFS-capable {PACKAGE_NAME} build from {GIT_REPOSITORY_URL}@{GIT_REVISION}...")
    environment = {**os.environ, _RECURSION_GUARD_ENV_VAR: "1"}
    for command in commands:
        try:
            result = subprocess.run(  # noqa: S603  command is built from module constants, not user input
                command,
                env=environment,
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=INSTALL_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            _enter_cooldown(state_dir)
            _notify(
                f"timed out updating {PACKAGE_NAME} to the RustFS-capable build; install it manually: "
                f"{INSTALL_REQUIREMENT}"
            )
            return
        except OSError as exc:
            _enter_cooldown(state_dir)
            _notify(f"could not run the {PACKAGE_NAME} update: {exc}")
            return
        if result.returncode != 0:
            _enter_cooldown(state_dir)
            detail = (result.stderr or result.stdout or "").strip()
            _notify(
                f"could not update {PACKAGE_NAME} to the RustFS-capable build (exit {result.returncode}): "
                f"{detail[-400:] or 'no output from the installer'}. Install it manually: {INSTALL_REQUIREMENT}"
            )
            return

    if not _installed_is_rustfs_build():
        _enter_cooldown(state_dir)
        _notify(
            f"the {PACKAGE_NAME} update reported success but the installed build still does not come from "
            f"{GIT_REPOSITORY_URL}@{GIT_REVISION}; run it manually: {INSTALL_REQUIREMENT}"
        )
        return

    _leave_cooldown(state_dir)
    # Clear the force flag so interpreters started from this one don't install again.
    os.environ.pop(FORCE_ENV_VAR, None)
    _adopt_installed_build()
    _notify(f"using {PACKAGE_NAME} from {GIT_REPOSITORY_URL}@{GIT_REVISION} (RustFS support)")


def _patch(state_dir: Path) -> None:
    """Repair the environment unless another process already did or is doing it."""
    lock = state_dir / LOCK_FILE_NAME
    if not _acquire_lock(lock):
        if _installed_is_rustfs_build():
            _adopt_installed_build()
            return
        _notify(
            f"another process is still updating {PACKAGE_NAME} to the RustFS-capable build; this run keeps "
            "the installed one (retry shortly if a command reports missing RustFS support)"
        )
        return
    try:
        # Re-check: whoever held the lock before us may have installed the build.
        if _needs_patch():
            _install(state_dir)
    finally:
        _release_lock(lock)


def _notify(message: str) -> None:
    """Report something the bootstrap actually did (or failed to do) to stderr.

    Staying silent on the happy path matters: this runs on every interpreter
    start in the environment, so routine chatter would land on unrelated
    commands, test runs and subprocesses.
    """
    with contextlib.suppress(OSError, ValueError):
        print(f"[oarepo-cli] {message}", file=sys.stderr)  # noqa: T201  stderr-only startup hook, no logging available


def bootstrap() -> None:
    """Install the RustFS-capable docker-services-cli build if this environment lacks it.

    Called from ``oarepo_cli_rustfs_bootstrap.pth`` during interpreter startup.
    Never raises: whatever happens, the interpreter keeps working and the
    currently installed docker-services-cli stays in place, where
    ``services.services_lifecycle`` turns missing RustFS support into a clear
    error message.
    """
    global _bootstrapped  # noqa: PLW0603  per-interpreter guard for a .pth hook line

    if _bootstrapped:
        return
    _bootstrapped = True
    if os.environ.get(_RECURSION_GUARD_ENV_VAR) or os.environ.get(SKIP_ENV_VAR):
        return
    if _running_under_pip():
        # A user- or CI-driven pip install is already mutating this
        # environment; don't start a competing installer under it.
        return
    try:
        if not _needs_patch():
            return
        state_dir = _state_dir()
        try:
            # A prefix we cannot write to is also a prefix the installer cannot
            # write to, so there is nothing to be done in that case.
            state_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return
        if _in_cooldown(state_dir):
            return
        _patch(state_dir)
    except Exception as exc:  # noqa: BLE001  never break interpreter startup, whatever happens
        _notify(f"skipped the {PACKAGE_NAME} RustFS bootstrap: {exc}")
