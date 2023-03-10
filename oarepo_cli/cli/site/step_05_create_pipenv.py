from pathlib import Path
import shutil

from pkg_resources import parse_requirements

from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.ui.radio import Radio
from oarepo_cli.ui.wizard import WizardStep

from ...utils import commit_git, run_cmdline


class CreatePipenvStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            Radio(
                "create_pipenv_in_site",
                options={
                    "yes": ".venv inside my site directory",
                    "no": "~/.config/virtualenvs/<mangled_name> (standard pipenv location)",
                },
                default="yes",
            ),
            heading="""
In this step I will create python environment for this repository.
Note that this can take a couple of minutes to finish
during which "Locking ..." will be displayed.

What is your preference of pipenv virtual environment location?
            """,
            **kwargs,
        )

    def after_run(self):
        site_dir = self.site_dir
        if self.data.get("create_pipenv_in_site") == "yes":
            (site_dir / ".venv").mkdir(parents=True, exist_ok=True)
        python_binary = shutil.which(self.data.whole_data["config"]["python"])
        run_cmdline(
            "pipenv",
            "lock",
            "--python",
            python_binary,
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
        run_cmdline(
            "pipenv",
            "install",
            "--python",
            python_binary,
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
        run_cmdline(
            "pipenv",
            "run",
            "which",
            "python",
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )

        pipenv_venv_dir = Path(self._pipenv_venv_dir).relative_to(self.data.project_dir)

        self.data["site_pipenv_dir"] = str(pipenv_venv_dir)
        commit_git(
            self.data.project_dir,
            f"after-site-pipenv-{self.data.section}",
            f"Committed automatically after site {self.data.section} pipenv has been called",
        )

    @property
    def _pipenv_venv_dir(self):
        success = run_cmdline(
            "pipenv",
            "--venv",
            cwd=self.site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
            check_only=True,
            grab_stdout=True,
        )
        if not success:
            return None
        return success.strip()

    def should_run(self):
        should_run = (
            "site_pipenv_dir" not in self.data
            or not (self.data.project_dir / self.data["site_pipenv_dir"]).exists()
        )
        if should_run:
            return should_run

        # the directory exists, fetch requirements and compare them
        pipfile_requirements = self.load_reqs(
            run_cmdline(
                "pipenv",
                "requirements",
                cwd=self.site_dir,
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
                check_only=True,
                grab_stdout=True,
            )
        )

        virtualenv_requirements = self.load_reqs(
            run_cmdline(
                "pipenv",
                "run",
                "pip",
                "freeze",
                cwd=self.site_dir,
                environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
                check_only=True,
                grab_stdout=True,
            )
        )

        IGNORED_PACKAGES = {"setuptools", "pip", "wheel"}

        requirement_not_found = False

        for key, pipfile_version in pipfile_requirements.items():
            virtualenv_version = virtualenv_requirements.get(key)
            if not virtualenv_version:
                if key in IGNORED_PACKAGES:
                    continue
                print(f"Requirement {key} not found, will run pipfile lock")
                requirement_not_found = True
            elif pipfile_version != virtualenv_version:
                print(
                    f"Requirement version mismatch in {key}. Expected {pipfile_version}, is {virtualenv_version}. Will run pipfile lock"
                )
                requirement_not_found = True

        return requirement_not_found

    def load_reqs(self, txt):
        ret = {}
        for l in txt.splitlines():
            l = l.strip()
            if l[0] == "-" or l[0] == "#":
                continue
            try:
                for resource in parse_requirements(l):
                    pn = resource.project_name.replace("_", "-").lower()
                    version = None
                    for spec in resource.specs:
                        if spec[0] == "==":
                            version = spec[1]
                    ret[pn] = version
            except Exception as e:
                print(f"Error parsing {l}: {e}")
        return ret
