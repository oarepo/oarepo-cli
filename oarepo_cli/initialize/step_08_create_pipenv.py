from pathlib import Path

from utils import run_cmdline

from oarepo_cli.ui.radio import Radio
from oarepo_cli.ui.wizard import WizardStep


class CreatePipenvStep(WizardStep):
    step_name = "create-pipenv"

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
        site_dir = str(Path(data["project_dir"]) / data["site_package"])
        if data["create_pipenv_in_site"] == "yes":
            (Path(data["project_dir"]) / data["site_package"] / ".venv").mkdir(
                parents=True, exist_ok=True
            )
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
