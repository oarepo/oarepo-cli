from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import ProjectWizardMixin
from oarepo_cli.wizard import WizardStep


def replace_non_variable_signs(x):
    return f"__{ord(x.group())}__"


class InstallToSiteStep(ProjectWizardMixin, WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        sites = self.data["sites"]
        for site in sites:
            SiteSupport(self.data, site).rebuild_site(build_ui=True)
