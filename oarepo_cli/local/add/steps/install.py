from oarepo_cli.site.install_site import update_and_install_site
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
            update_and_install_site(self.data, site)
