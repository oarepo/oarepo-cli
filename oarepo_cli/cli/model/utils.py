import os
from pathlib import Path

from oarepo_cli.cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.utils import find_oarepo_project


def load_model_repo(model_name, project_dir):
    project_dir = find_oarepo_project(project_dir)
    if not model_name:
        model_name = Path(os.getcwd()).name
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=["models", model_name])
    cfg.load()
    cfg["model_name"] = model_name
    return cfg, project_dir


def get_model_dir(data):
    return data.project_dir / "models" / data["model_name"]


class ModelWizardStep(SiteMixin, ProjectWizardMixin, WizardStep):
    def model_name(self, data):
        return data.section

    def model_dir(self, data):
        return data.project_dir / "models" / self.model_name(data)

    def model_package_dir(self, data):
        return self.model_dir(data) / data["model_package"]
