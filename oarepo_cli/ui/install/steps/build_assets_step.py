from oarepo_cli.assets import build_assets
from oarepo_cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.wizard import WizardStep


class BuildAssetsUIStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data["sites"]
        for site_name in sites:
            build_assets(cfg=self.data, site_name=site_name)
