from pathlib import Path


class SiteWizardStepMixin:
    @property
    def site_dir(self):
        return Path(self.data.project_dir) / self.data["site_dir"]
