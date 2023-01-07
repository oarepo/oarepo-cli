import os
from pathlib import Path

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.utils import find_oarepo_project, run_cmdline


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


class ProjectWizardMixin:
    def site_dir(self, data):
        if not hasattr(self, "site"):
            raise Exception("Current site not set")
        return data.project_dir / self.site["site_dir"]

    def invenio_cli(self, data):
        return data.project_dir / data.get("config.invenio_cli")

    def invenio_cli_command(self, data, *args, cwd=None, environ=None):
        return run_cmdline(
            self.invenio_cli(data),
            *args,
            cwd=cwd or self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )

    def pipenv_command(self, data, *args, cwd=None, environ=None):
        return run_cmdline(
            "pipenv",
            *args,
            cwd=cwd or self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )

    def invenio_command(self, data, *args, cwd=None, environ=None):
        return run_cmdline(
            "pipenv",
            "run",
            "invenio",
            *args,
            cwd=cwd or self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )


class ModelWizardStep(ProjectWizardMixin, WizardStep):
    def model_name(self, data):
        return data.section

    def model_dir(self, data):
        return data.project_dir / "models" / self.model_name(data)

    def model_package_dir(self, data):
        return self.model_dir(data) / data["model_package"]

    def site_dir(self, data):
        site_name = data.get("installation_site", None)
        if not site_name:
            raise Exception("Unexpected error: No installation site specified")
        site = data.get(f"sites.{site_name}")
        if not site:
            raise Exception(
                f"Unexpected error: Site with name {site_name} does not exist"
            )
        return data.project_dir / site["site_dir"]
