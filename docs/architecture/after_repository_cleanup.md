# Post-Phase-4 Sanity Check: `library` vs `repository` Command Parity

**Status**: Audit only — nothing here has been implemented yet. This document
records a comparison of `oarepo_cli/cli/library.py` and
`oarepo_cli/cli/repository.py` against each other and against the two real
bash scripts (`library_runner.sh`, `repository_runner.sh`), done after Phase
4 (repository commands) was completed, to catch drift/inconsistencies before
starting Phase 5. Each item below should become its own step (or be folded
into an existing one) in [implementation-steps.md](./implementation-steps.md)
once triaged.

## 1. Command inventory — library vs repository

| Area | `library` | `repository` | Verdict |
|---|---|---|---|
| Env setup | `venv`, `install`, `clean`, `upgrade` | `install`, `upgrade` | Repository never had `venv`/`clean` in bash either — intentional, not a gap |
| Services | `start`, `stop` (top-level) | `services setup/start/stop/destroy` (subgroup) | Faithful to both bash scripts' own shapes — asymmetric but correct |
| Passthrough | `shell`, `invenio` | `cli` (→ invenio-cli) | Real gap — see §3.1 |
| Dev tooling | `lint`, `format`, `check`, `license-headers`, `jslint`, `jstest`, `test`, `translations`, `oarepo-versions` | `translations` only | Bash never gave the repository runner any of these either — intentional split (library = package dev tooling, repository = deployed instance). Not a bug, but see §4 |
| Repository-only | — | `run`, `model`, `local`, `index rebuild`, `reset`, `info` | Correct, no library analog needed (instance-lifecycle concepts) |
| Dropped from both | `self-update` | `self-update` | Deliberately dropped in both, consistent |

## 2. Verified bugs (not just asymmetry)

### 2.1 `library clean` prints its summary twice

`oarepo_cli/cli/library.py` (around lines 314-340) has the entire "Display
summary" if/else block duplicated verbatim — a copy-paste artifact. Every
`library clean` run prints `✨ ✓ Cleanup completed...` (or `already clean`)
twice. Trivial, unambiguous fix: delete the second copy.

### 2.2 Inconsistent exception handling between the two modules

Every command in `library.py` (17 sites) catches broad `except Exception`;
every command in `repository.py` (12 sites) catches narrow
`except (OARepoError, ProcessExecutionError)`. `repository.py` (Phase 4,
written later) established a stricter pattern that was never backported to
`library.py` (Phase 3).

Practical effect: a real bug in a `library` command (e.g. an
`AttributeError`) gets silently turned into a clean `exit 1` with a
misleading `❌ Error running linters: ...`-style message instead of
surfacing a traceback, whereas the same class of bug in a `repository`
command propagates and crashes loudly (traceback visible).

**Action needed**: pick one policy and apply it uniformly across both
modules. Leaning towards narrowing `library.py` to match `repository.py`,
since broad catches mask real bugs — but confirm before a mechanical
17-site change.

Minor bonus nit found while checking this: `ProcessExecutionError` already
subclasses `OARepoError` (`core/errors.py`), so `repository.py`'s
`except (OARepoError, ProcessExecutionError)` is redundant —
`except OARepoError` alone is equivalent. Cosmetic only, fix opportunistically
if touching those lines anyway.

### 2.3 `library oarepo-versions` bypasses the shared context/config layer

It's the *only* command (of 31 total across both modules) that doesn't call
`discover_context()`. Instead it hand-rolls its own parent-directory walk to
find `pyproject.toml` and wires up `PyProjectReader`/`VersionResolver`
directly (`cli/library.py`, in `library_oarepo_versions`). It also has
function-local imports (`json`, `Path`, `ConfigurationError`,
`PyProjectReader`, `VersionResolver`) that aren't there to break a circular
import — they were just never hoisted, violating AGENTS.md's "no imports
inside a function unless breaking circular imports" rule.

**Action needed**: refactor to use `discover_context()` like every other
command, and hoist the imports to module level — but first verify
`discover_context()`'s failure mode still meets `oarepo-versions`' contract
(it may be intentionally lenient about missing venv/config since it only
needs `pyproject.toml`, not a fully resolved project).

### 2.4 `library_shell` also has a function-local import

`import traceback  # noqa: TID251` inside its `except Exception` branch
(`cli/library.py`, in `library_shell`) — same AGENTS.md rule violation,
deliberately noqa'd. `repository.py` has no equivalent instance anywhere.

## 3. Real capability gaps vs the original bash scripts

### 3.1 No `repository invenio` (bare invenio passthrough)

`repository_runner.sh` has `run.sh invenio <args>`
(`activate_venv; invenio "$@"`), distinct from `cli` (which maps to
`invenio-cli`). `library invenio` has a direct analog already. This was
deliberately scoped out in Step 4.10 (see its deviation note in
[implementation-steps.md](./implementation-steps.md)) specifically *because*
it's absent from `00-main-architecture.md`'s and `03-migration-guide.md`'s
command tables — but it's a real, working bash feature nobody ported.

`services/repository.py` already has `get_invenio_binary()` and an internal
`_run_invenio()` helper (used by `rebuild_index`/`reset_repository`), so
adding a CLI-exposed `repository invenio` passthrough (mirroring `cli`'s
`os.execve`-based approach) would be small.

## 4. Open product question (not a bug)

The dev-tooling commands (`lint`/`format`/`check`/`jslint`/`jstest`/
`license-headers`/`test`) exist only for `library` in both the old bash
scripts and the current rewrite, because a "repository" in this design is a
deployed instance, not a distributable package. If that's still the intended
shape, no repository-side work is needed here.

If `repository lint`/`format`/etc. should actually exist (some repositories
carry custom Python code — models, extensions), that's new scope beyond
what bash ever did, not a missing-implementation bug, and should be
discussed/scoped as its own step rather than assumed.

## Suggested next steps, roughly in priority order

1. Fix the `library clean` duplicate-print bug (§2.1) — trivial, no design
   decision needed.
2. Decide the exception-handling policy (§2.2) and apply it uniformly.
3. Refactor `library_oarepo_versions` to use `discover_context()` (§2.3) and
   hoist its imports; fix `library_shell`'s local import (§2.4).
4. Decide whether to add `repository invenio` for bash parity (§3.1).
5. Confirm whether repository-side lint/format tooling is in scope at all
   (§4) before doing any work there.

**Triage outcome**: all of the above are now planned as
[implementation-steps.md](./implementation-steps.md) Steps 4.11-4.20 --
4.11-4.14 cover §2.1-2.4 (the four verified bugs above), narrowing exception
handling was decided in favor of `repository.py`'s pattern (§2.2), and
4.15-4.20 cover `repository invenio`/`shell` plus porting `lint`/`format`/
`check`/`jslint`/`jstest`/`test` to `repository` (§3.1 and §4, both resolved
as "yes, add them" -- §4's open question is no longer open).
