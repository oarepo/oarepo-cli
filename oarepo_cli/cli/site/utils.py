from pathlib import Path


class SiteWizardStepMixin:
    def site_dir(self, data):
        return Path(data.get("config.project_dir")) / data["site_dir"]
