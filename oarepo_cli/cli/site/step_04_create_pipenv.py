from pathlib import Path
from oarepo_cli.cli.site.utils import SiteWizardStepMixin

from oarepo_cli.ui.radio import Radio
from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline


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
            **kwargs
        )

    def after_run(self, data):
        site_dir = self.site_dir(data)
        if data.get("create_pipenv_in_site") == "yes":
            (site_dir / ".venv").mkdir(parents=True, exist_ok=True)
        run_cmdline(
            "pipenv", "lock", cwd=site_dir, environ={"PIPENV_IGNORE_VIRTUALENVS": "1"}
        )
        run_cmdline(
            "pipenv",
            "install",
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

        pipenv_venv_dir = self._get_pipenv_venv_dir(data)

        data["site_pipenv_dir"] = pipenv_venv_dir

    def _get_pipenv_venv_dir(self, data):
        success = run_cmdline(
            "pipenv",
            "--venv",
            cwd=self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
            check_only=True,
            grab_stdout=True,
        )
        if not success:
            return None
        return success.strip()

    def should_run(self, data):
        return (
            "site_pipenv_dir" not in data or not Path(data["site_pipenv_dir"]).exists()
        )
