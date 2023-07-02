from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class InstallInvenioStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, clean=False, **kwargs):
        super().__init__(
            heading="""
Now I'll install invenio site.
            """,
            **kwargs,
        )
        self.clean = clean

    def after_run(self):
        self.site_support.check_and_create_virtualenv(clean=self.clean)

        self.site_support.install_site()

    def should_run(self):
        return True
