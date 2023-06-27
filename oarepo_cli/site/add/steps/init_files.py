from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class InitFilesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
        Now I will configure the default location for files storage in the minio s3 framework.
            """,
            **kwargs,
        )

    def after_run(self):
        self.site_support.init_files()

    def should_run(self):
        return not self.site_support.check_file_location_initialized(raise_error=False)
