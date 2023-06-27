import json
import shutil

from oarepo_cli.utils import run_cmdline
from oarepo_cli.wizard import WizardStep


class UpgradeNRPStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        for venv_dir in (self.data.project_dir / ".venv").glob("*"):
            if not venv_dir.is_dir():
                continue
            if venv_dir.name == "oarepo-model-builder":
                shutil.rmtree(venv_dir)
                continue
            if not (venv_dir / "bin" / "python").exists():
                continue
            upgrade_venv(venv_dir)


def upgrade_venv(venv_dir):
    # run
    packages = run_cmdline(
        "./bin/pip",
        "list",
        "--outdated",
        "--format",
        "json",
        cwd=venv_dir,
        grab_stdout=True,
        grab_stderr=False,
        raise_exception=True,
    )
    packages = json.loads(packages)
    obsolete_packages = [
        f"{p['name']}=={p['latest_version']}"
        for p in packages
        if p["name"].startswith("oarepo") or p["name"].startswith("nrp")
    ]
    if obsolete_packages:
        run_cmdline(
            "./bin/pip",
            "install",
            "-U",
            *obsolete_packages,
            cwd=venv_dir,
            raise_exception=True,
        )
