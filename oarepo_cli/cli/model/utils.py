import os

from oarepo_cli.cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.ui.wizard import WizardStep


class ModelWizardStep(SiteMixin, ProjectWizardMixin, WizardStep):
    @property
    def model_name(self):
        return self.data.section

    @property
    def model_dir(self):
        return self.data.project_dir / "models" / self.model_name

    @property
    def model_package_dir(self):
        return self.model_dir / os.sep.join(self.data["model_package"].split("."))
