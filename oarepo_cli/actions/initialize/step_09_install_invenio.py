from pathlib import Path

from oarepo_cli.actions.utils import run_cmdline
from oarepo_cli.ui.wizard import WizardStep


class InstallInvenioStep(WizardStep):
    step_name = "install-invenio"

    def __init__(self, **kwargs):
        super().__init__(
            heading="""
Now I'll install invenio libraries from site's Pipfile. 
Note that this can take a lot of time as UI dependencies
will be downloaded and installed and UI will be compiled.
            """,
            **kwargs
        )

    def after_run(self, data):
        site_dir = str(Path(data["project_dir"]) / data["site_package"])
        run_cmdline(data["invenio_cli"], "install", cwd=site_dir,
                    environ={
                        'PIPENV_IGNORE_VIRTUALENVS': '1'
                    })
