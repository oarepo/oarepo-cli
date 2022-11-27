from pathlib import Path

from oarepo_cli.actions.utils import run_cmdline
from oarepo_cli.ui.wizard import WizardStep


class CreatePipenvStep(WizardStep):
    step_name = "create-pipenv"

    def __init__(self, **kwargs):
        super().__init__(
            heading="""
In this step I will create python environment for this repository.
Note that this can take a couple of minutes to finish
during which "Locking ..." will be displayed.
            """,
            **kwargs
        )

    def after_run(self, data):
        site_dir = str(Path(data["project_dir"]) / data["site_package"])
        run_cmdline("pipenv", "lock", cwd=site_dir,
                    environ={
                        'PIPENV_IGNORE_VIRTUALENVS': '1'
                    })
        run_cmdline("pipenv", "install", cwd=site_dir,
                    environ={
                        'PIPENV_IGNORE_VIRTUALENVS': '1'
                    })
        run_cmdline("pipenv", "run", "which", "python", cwd=site_dir,
                    environ={
                        'PIPENV_IGNORE_VIRTUALENVS': '1'
                    })
