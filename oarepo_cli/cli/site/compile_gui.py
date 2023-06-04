from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep
from ..develop_docker import build_assets

from ...utils import commit_git, run_cmdline


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
        build_assets(virtualenv=self.site_dir / '.venv',
                     invenio=self.site_dir / '.venv' / 'var' / 'instance',
                     cwd=self.site_dir)

    def should_run(self):
        manifest_file = self._manifest_file
        return not manifest_file.exists()

    @property
    def _manifest_file(self):
        manifest_file = (
            self.site_dir / '.venv.' / "var" / "instance" / "static" / "dist" / "manifest.json"
        )

        return manifest_file
