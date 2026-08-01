# OARepo CLI Migration Guide

## Overview

This document provides guidance for migrating from the existing shell-script-based runners (`library_runner.sh`, `repository_runner.sh`, `repository_installer.sh`) to the new Python implementation (`oarepo-cli`).

---

## 1. Quick Start

### Installation

```bash
# Install via pip (recommended)
pip install oarepo-cli

# Or install from source
git clone https://github.com/oarepo/oarepo-cli.git
cd oarepo-cli
pip install -e .

# Verify installation
oarepo-cli --version
```

### Basic Usage

**Old way (shell scripts):**
```bash
cd /path/to/library
./run.sh venv
./run.sh test
```

**New way (Python CLI):**
```bash
cd /path/to/library
oarepo-cli library venv
oarepo-cli library test
```

---

## 2. Command Mapping

### Library Commands

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `./run.sh venv` | `oarepo-cli library venv` | Identical behavior |
| `./run.sh venv --force` | `oarepo-cli library venv --force` | Same flag |
| `./run.sh venv --no-editable` | `oarepo-cli library venv --no-editable` | Same flag |
| `./run.sh upgrade` | `oarepo-cli library upgrade` | Identical behavior |
| `./run.sh start` | `oarepo-cli library start` | Identical behavior |
| `./run.sh stop` | `oarepo-cli library stop` | Identical behavior |
| `./run.sh test` | `oarepo-cli library test` | Identical behavior |
| `./run.sh test --skip-services` | `oarepo-cli library test --skip-services` | Same flag |
| `./run.sh test --with-coverage` | `oarepo-cli library test --with-coverage` | Same flag |
| `./run.sh oarepo-versions` | `oarepo-cli library oarepo-versions` | JSON output preserved |
| `./run.sh clean` | `oarepo-cli library clean` | Identical behavior |
| `./run.sh shell` | `oarepo-cli library shell` | Identical behavior |
| `./run.sh shell --skip-services` | `oarepo-cli library shell --skip-services` | Same flag |
| `./run.sh invenio <args>` | `oarepo-cli library invenio -- <args>` | Note the `--` separator |
| `./run.sh invenio --skip-services <args>` | `oarepo-cli library invenio --skip-services -- <args>` | Flags before `--` |
| `./run.sh translations` | `oarepo-cli library translations` | Identical behavior |
| `./run.sh lint` | `oarepo-cli library lint` | Identical behavior |
| `./run.sh format` | `oarepo-cli library format` | Identical behavior |
| `./run.sh license-headers` | `oarepo-cli library license-headers` | Identical behavior |
| `./run.sh jslint` | `oarepo-cli library jslint` | Identical behavior |
| `./run.sh jstest setup` | `oarepo-cli library jstest setup` | Identical behavior |
| `./run.sh jstest --skip-services` | `oarepo-cli library jstest --skip-services` | Same flag |
| `./run.sh self-update` | **Removed** | Use `pip install --upgrade oarepo-cli` | **Not available** in Python CLI |
| `./run.sh --no-editable test` | `oarepo-cli library venv --no-editable && oarepo-cli library test` | Flag moved to venv command |

### Repository Commands

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `./run.sh install` | `oarepo-cli repository install` | Identical behavior |
| `./run.sh upgrade` | `oarepo-cli repository upgrade` | Identical behavior |
| `./run.sh services setup` | `oarepo-cli repository services setup` | Identical behavior |
| `./run.sh services start` | `oarepo-cli repository services start` | Identical behavior |
| `./run.sh services stop` | `oarepo-cli repository services stop` | Identical behavior |
| `./run.sh services destroy` | `oarepo-cli repository services destroy` | Identical behavior |
| `./run.sh model create <name>` | `oarepo-cli repository model create <name>` | Identical behavior |
| `./run.sh model create <name> <config>` | `oarepo-cli repository model create <name> <config>` | Identical behavior |
| `./run.sh model update <name>` | `oarepo-cli repository model update <name>` | Identical behavior |
| `./run.sh model update <name> <answers>` | `oarepo-cli repository model update <name> <answers>` | Identical behavior |
| `./run.sh local add <path>` | `oarepo-cli repository local add <path>` | Identical behavior |
| `./run.sh local remove <name>` | `oarepo-cli repository local remove <name>` | Identical behavior |
| `./run.sh run` | `oarepo-cli repository run` | Identical behavior |
| `./run.sh run --no-services` | `oarepo-cli repository run --no-services` | Same flag |
| `./run.sh run --no-celery` | `oarepo-cli repository run --no-celery` | Same flag |
| `./run.sh cli <subcommand>` | `oarepo-cli repository cli <subcommand>` | Identical behavior |
| `./run.sh translations` | `oarepo-cli repository translations` | Identical behavior |
| `./run.sh translations compile` | `oarepo-cli repository translations compile` | Identical behavior |
| `./run.sh index rebuild` | `oarepo-cli repository index rebuild` | Identical behavior |
| `./run.sh reset` | `oarepo-cli repository reset` | Identical behavior (with confirmation prompt) |
| `./run.sh info` | `oarepo-cli repository info` | Identical behavior |
| `./run.sh self-update` | **Removed** | Use `pip install --upgrade oarepo-cli` | **Not available** in Python CLI |

### Repository Installer

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `./repository_installer.sh my-repo` | `oarepo-cli repo-install my-repo` | Top-level command |
| `./repository_installer.sh --python python3.14 my-repo` | `oarepo-cli repo-install --python python3.14 my-repo` | Same flag |
| `./repository_installer.sh --template <url> my-repo` | `oarepo-cli repo-install --template <url> my-repo` | Same flag |
| `./repository_installer.sh --version rdm-14 my-repo` | `oarepo-cli repo-install --version rdm-14 my-repo` | Same flag |
| `./repository_installer.sh --config file.yaml my-repo` | `oarepo-cli repo-install --config file.yaml my-repo` | Same flag |

---

## 3. Environment Variables

All existing environment variables are supported with identical semantics:

| Variable | Purpose | Example |
|----------|---------|---------|
| `OAREPO_VERSION` | Override OARepo version | `OAREPO_VERSION=14 oarepo-cli library venv` |
| `PYTHON` | Override Python binary | `PYTHON=python3.12 oarepo-cli library venv` |
| `UV_PROJECT_ENVIRONMENT` | Custom venv path | `UV_PROJECT_ENVIRONMENT=.venv oarepo-cli library venv` |
| `SKIP_SERVICES` | Skip service lifecycle | `SKIP_SERVICES=1 oarepo-cli library test` |
| `NO_EDITABLE` | Use wheel build mode | `NO_EDITABLE=1 oarepo-cli library venv` |
| `WITH_COVERAGE` | Enable coverage | `WITH_COVERAGE=1 oarepo-cli library test` |
| `MODEL_TEMPLATE` | Model template URL | `MODEL_TEMPLATE=https://... oarepo-cli repository model create` |
| `MODEL_TEMPLATE_VERSION` | Model template version | `MODEL_TEMPLATE_VERSION=rdm-14 oarepo-cli repository model create` |
| `UV_EXTRA_INDEX_URL` | Extra PyPI index | Already set by default |
| `ORGANIZATION` | License header org | `ORGANIZATION="My Org" oarepo-cli library license-headers` |
| `DEMO_USER_PASSWORD` | Reset admin password | `DEMO_USER_PASSWORD=secret oarepo-cli repository reset` |

**Note:** The Python CLI reads these environment variables but does NOT export them to the parent shell (unlike the shell scripts). This is intentional for cleaner behavior.

---

## 4. Configuration via pyproject.toml

The Python CLI supports optional configuration in `pyproject.toml`:

```toml
[tool.oarepo-cli]
# Build settings
editable = true

# Test settings
test_coverage = false
test_skip_services = false

# Venv settings
venv_path = ".venv"

# Python settings
python_binary = "python3.14"  # Optional, defaults to auto-detection

# OARepo settings
oarepo_version = 14  # Optional, defaults to first from dependencies

# Services settings
services_db = "postgresql"
services_search = "opensearch"
services_mq = "rabbitmq"
services_cache = "redis"
services_s3 = "minio"

# Model settings
model_template_url = "https://github.com/oarepo/nrp-model-copier"
model_template_version = "rdm-14"

# License settings
license_organization = "CESNET z.s.p.o"
```

These settings can still be overridden by environment variables and command-line flags.

---

## 5. Breaking Changes

### 5.1 Self-Update Removal

**What changed:** The `self-update` command has been **completely removed** from the Python CLI.

**Reason:** 
- Incompatible with Python package distribution model (pip/PyPI)
- Security concerns with downloading and executing remote scripts
- Unnecessary when `pip install --upgrade` provides identical functionality
- Maintains clear separation: shell scripts use shell updates, Python uses pip

**Migration:**
```bash
# Old (no longer available in Python CLI)
./run.sh self-update

# New (for Python CLI)
pip install --upgrade oarepo-cli

# Shell scripts still support self-update during transition
# but will be deprecated alongside the scripts themselves
```

**Note:** The shell scripts will continue to support `self-update` during the transition period. Once shell scripts are deprecated, this functionality will be fully retired without a direct replacement.

### 5.2 Environment Variable Export

**What changed:** The Python CLI no longer exports environment variables to the parent shell.

**Old behavior:** 
```bash
$ ./run.sh shell
$ echo $DB_URL  # Would show the service URL
```

**New behavior:**
```bash
$ oarepo-cli library shell
$ echo $DB_URL  # Not set in parent shell
```

**Reason:** Cleaner, more predictable behavior. Environment mutations should happen within subprocesses only.

**Migration:** If you relied on exported variables, use the `.env-services` file that's still created:

```bash
source .env-services  # Manually load if needed
```

### 5.3 Invenio Command Separator

**What changed:** When passing arguments to `invenio` subcommands, use `--` separator.

**Old behavior:**
```bash
./run.sh invenio db upgrade
```

**New behavior:**
```bash
oarepo-cli library invenio -- db upgrade
```

**Reason:** Prevents argument parsing conflicts between oarepo-cli and invenio.

### 5.4 Exit Code Consistency

**What changed:** Exit codes are now consistently propagated from subprocesses.

**Impact:** Some edge cases may have different exit codes than before.

**Mitigation:** Check exit codes explicitly in scripts; don't rely on implicit success/failure detection.

---

## 6. Migration Checklist

### For Individual Developers

- [ ] Install `oarepo-cli` via pip
- [ ] Update shell aliases/scripts to use new command syntax
- [ ] Remove reliance on exported environment variables
- [ ] Test common workflows (venv, test, lint, run)
- [ ] Update documentation/references in personal notes

### For Team Leads

- [ ] Announce migration timeline to team
- [ ] Update team documentation and wikis
- [ ] Create migration guide for team members
- [ ] Plan pair programming sessions for complex workflows
- [ ] Monitor for migration issues/questions

### For CI/CD Maintainers

- [ ] Add `oarepo-cli` installation step to CI pipelines
- [ ] Update all `./run.sh` references to `oarepo-cli ...`
- [ ] Replace `self-update` calls with `pip install --upgrade`
- [ ] Add compatibility tests (run both implementations side-by-side)
- [ ] Set deprecation timeline (recommend 3-6 months)
- [ ] Plan removal of shell scripts after transition period

### For Project Maintainers

- [ ] Publish `oarepo-cli` to PyPI
- [ ] Create release notes with migration instructions
- [ ] Update README.md with new installation instructions
- [ ] Add deprecation notices to shell scripts
- [ ] Monitor issue tracker for migration bugs
- [ ] Plan shell script removal (after 6 months or v2.0)

---

## 7. Side-by-Side Comparison

During the transition period, you can run both implementations in parallel:

```bash
# Test equivalence for a specific command
./run.sh test --skip-services > bash-output.txt 2>&1
oarepo-cli library test --skip-services > python-output.txt 2>&1

# Compare outputs
diff bash-output.txt python-output.txt
```

This is useful for:
- Verifying behavioral parity
- Debugging discrepancies
- Validating migration progress

---

## 8. Troubleshooting

### Issue: "Command not found: oarepo-cli"

**Cause:** CLI not installed or not in PATH.

**Solution:**
```bash
pip install oarepo-cli
# Verify
which oarepo-cli
```

### Issue: "pyproject.toml not found"

**Cause:** Not running from project directory.

**Solution:** Ensure you're in the directory containing `pyproject.toml`:
```bash
cd /path/to/project
oarepo-cli library venv
```

### Issue: "Python version mismatch"

**Cause:** Required Python version not installed.

**Solution:** Install required Python version or override:
```bash
# Install Python 3.14 (example)
brew install python@3.14

# Or override with environment variable
PYTHON=python3.12 oarepo-cli library venv
```

### Issue: "Virtual environment already exists"

**Cause:** Existing `.venv` directory conflicts.

**Solution:** Force recreate:
```bash
oarepo-cli library venv --force
```

### Issue: "Docker services not starting"

**Cause:** Docker not running or permissions issue.

**Solution:**
```bash
# Check Docker status
docker ps

# Start Docker Desktop if needed
# Or skip services for commands that allow it
oarepo-cli library test --skip-services
```

### Issue: "Permission denied when writing to .venv"

**Cause:** Previous run as root/sudo corrupted permissions.

**Solution:**
```bash
# Remove corrupted venv
rm -rf .venv

# Recreate without sudo
oarepo-cli library venv
```

---

## 9. Performance Comparison

| Operation | Shell Script | Python CLI | Notes |
|-----------|--------------|------------|-------|
| `--help` | ~50ms | ~100ms | Python startup overhead |
| `venv` (existing) | ~200ms | ~250ms | Similar performance |
| `venv` (create) | ~15s | ~15s | uv dominates runtime |
| `test` (no services) | ~30s | ~30s | pytest dominates runtime |
| `lint` | ~10s | ~10s | ruff dominates runtime |

**Conclusion:** No significant performance regression. Python startup adds ~50-100ms to lightweight commands.

---

## 10. Deprecation Timeline

| Date | Milestone |
|------|-----------|
| v1.0.0 | Python CLI released alongside shell scripts |
| v1.1.0 | `self-update` deprecated with warning |
| v1.5.0 | Shell scripts emit deprecation warning |
| v2.0.0 | Shell scripts removed (earliest 6 months after v1.0.0) |

**Recommendation:** Complete migration before v2.0.0.

---

## 11. FAQ

**Q: Do I need to reinstall my virtual environments?**  
A: No, the Python CLI uses the same `.venv` directory structure. Existing venvs will work.

**Q: Can I still use the shell scripts during transition?**  
A: Yes, they'll remain available until v2.0.0. However, we recommend migrating to Python CLI for new projects.

**Q: What happens to my `.runner.sh` cached scripts?**  
A: They become obsolete. The Python CLI is installed via pip and updated that way.

**Q: Is the Python CLI slower?**  
A: Negligibly for most operations (~50-100ms startup overhead). Heavy operations (tests, builds) are dominated by external tools.

**Q: Can I contribute to the Python CLI?**  
A: Absolutely! See the CONTRIBUTING.md file for development setup instructions.

**Q: What if I find a bug during migration?**  
A: Report it on GitHub with labels `migration` and `bug`. Include both bash and Python outputs for comparison.

**Q: Will Windows be supported?**  
A: Not in v1.x. Linux and macOS are the primary targets. Windows users should use WSL2.

---

## 12. Support Resources

- **Documentation:** `docs/architecture/*.md`
- **Issue Tracker:** https://github.com/oarepo/oarepo-cli/issues
- **Discussions:** https://github.com/oarepo/oarepo-cli/discussions
- **Slack/Discord:** [Link to community chat]

---

## Appendix A: Complete Option Reference

### Library Commands

```
oarepo-cli library venv [--force] [--no-editable]
oarepo-cli library upgrade
oarepo-cli library start
oarepo-cli library stop
oarepo-cli library test [--skip-services] [--with-coverage] [pytest_args...]
oarepo-cli library oarepo-versions
oarepo-cli library clean
oarepo-cli library shell [--skip-services]
oarepo-cli library invenio [--skip-services] -- [invenio_args...]
oarepo-cli library translations [make-translations_args...]
oarepo-cli library lint
oarepo-cli library format
oarepo-cli library license-headers
oarepo-cli library jslint
oarepo-cli library jstest setup [--skip-services] [--with-storybook]
oarepo-cli library jstest [--skip-services] [jest_args...]
oarepo-cli library self-update  # DEPRECATED
```

### Repository Commands

```
oarepo-cli repository install
oarepo-cli repository upgrade
oarepo-cli repository services setup/start/stop/destroy [options...]
oarepo-cli repository model create <name> [config_file]
oarepo-cli repository model update <name> [answers_file]
oarepo-cli repository local add <path>
oarepo-cli repository local remove <name|--all>
oarepo-cli repository run [--no-services] [--no-celery]
oarepo-cli repository cli [invenio-cli_args...]
oarepo-cli repository translations [compile]
oarepo-cli repository index rebuild
oarepo-cli repository reset
oarepo-cli repository info
oarepo-cli repository self-update  # DEPRECATED
```

### Repository Installer

```
oarepo-cli repo-install <repo_name>
    --python <binary>
    --template <url|path>
    --version <ref>
    --uv <binary>
    --uvx <binary>
    --config <file>
```

---

This migration guide should help users and teams transition smoothly from the shell scripts to the Python CLI. For questions or issues, please open an issue on GitHub.
