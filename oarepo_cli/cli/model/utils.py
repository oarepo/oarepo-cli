import os
from pathlib import Path

from oarepo_cli.cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.utils import find_oarepo_project


class ModelWizardStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def model_name(self, data):
        return data.section

    def model_dir(self, data):
        return data.project_dir / "models" / self.model_name(data)

    def model_package_dir(self, data):
        return self.model_dir(data) / data["model_package"]
