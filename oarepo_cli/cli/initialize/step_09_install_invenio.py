from pathlib import Path

from oarepo_cli.ui.wizard import WizardStep

from ...utils import run_cmdline


class InstallInvenioStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
Now I'll install invenio site.

Note that this can take a lot of time as UI dependencies
will be downloaded and installed and UI will be compiled.
            """,
            **kwargs
        )

    def after_run(self, data):
        site_dir = str(Path(data["project_dir"]) / data["site_package"])
        run_cmdline(
            data["invenio_cli"],
            "install",
            cwd=site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )

    def should_run(self, data):
        # TODO: add check here
        return True
