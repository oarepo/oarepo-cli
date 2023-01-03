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
        if not self._get_manifest_file(data).exists():
            raise Exception(
                "invenio-cli install has not created var/instance/static/dist/manifest.json."
                "Please check the output, correct errors and run this command again"
            )

    def _site_dir(self, data):
        return str(Path(data["project_dir"]) / data["site_package"])

    def _get_pipenv_venv_dir(self, data):
        success = run_cmdline(
            "pipenv",
            "--venv",
            cwd=self._site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
            check_only=True,
            grab_stdout=True,
        )
        if not success:
            return None
        return success.strip()

    def should_run(self, data):
        manifest_file = self._get_manifest_file(data)
        return not manifest_file.exists()

    def _get_manifest_file(self, data):
        pipenv_dir = data["site_pipenv_dir"]
        manifest_file = (
            Path(pipenv_dir) / "var" / "instance" / "static" / "dist" / "manifest.json"
        )

        return manifest_file
