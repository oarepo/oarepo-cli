from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.ui.wizard import WizardStep

from ...utils import commit_git, run_cmdline


class InstallInvenioStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
Now I'll install invenio site.

Note that this can take a lot of time as UI dependencies
will be downloaded and installed and UI will be compiled.
            """,
            **kwargs,
        )

    def after_run(self):
        run_cmdline(
            self.data.project_dir / self.data.get("config.invenio_cli"),
            "install",
            cwd=self.site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
        if not self._manifest_file.exists():
            raise FileNotFoundError(
                "invenio-cli install has not created var/instance/static/dist/manifest.json."
                "Please check the output, correct errors and run this command again"
            )
        commit_git(
            self.data.project_dir,
            f"after-site-invenio-cli-install-{self.data.section}",
            f"Committed automatically after site {self.data.section} has been installed",
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
        manifest_file = self._manifest_file
        return not manifest_file.exists()

    @property
    def _manifest_file(self):
        pipenv_dir = self.data.project_dir / self.data["site_pipenv_dir"]
        manifest_file = (
            pipenv_dir / "var" / "instance" / "static" / "dist" / "manifest.json"
        )

        return manifest_file
