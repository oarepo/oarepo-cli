from oarepo_cli.old_cli.develop_docker import build_assets
from oarepo_cli.site.install_site import update_and_install_site
from oarepo_cli.utils import SiteMixin, ProjectWizardMixin
from oarepo_cli.wizard import WizardStep


class BuildAssetsUIStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data["sites"]
        for site in sites:
            site_dir = self.data.project_dir / 'sites' / site
            build_assets(
                virtualenv= site_dir / ".venv",
                invenio=site_dir / ".venv" / "var" / "instance",
                cwd=site_dir,
            )
