from oarepo_cli.assets import build_assets
from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class CompileGUIStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
Now I'll compile Invenio GUI.

Note that this can take a lot of time as UI dependencies
will be downloaded and installed and UI will be compiled.
            """,
            **kwargs,
        )

    def after_run(self):
        build_assets(
            cfg=self.data,
            site_name=self.data.section_path[-1],
        )

    def should_run(self):
        manifest_file = self._manifest_file
        return not manifest_file.exists()

    @property
    def _manifest_file(self):
        manifest_file = (
            self.site_dir
            / ".venv."
            / "var"
            / "instance"
            / "static"
            / "dist"
            / "manifest.json"
        )

        return manifest_file
