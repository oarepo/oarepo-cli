import os
from pathlib import Path

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import run_cmdline


class SiteSupport:
    def __init__(self, config: MonorepoConfig, site_section=None):
        self.config = config
        if config.section_path[0] == "sites":
            self.site = config
            return
        elif not site_section:
            sites = config.whole_data.get("sites", {})
            if len(sites) == 1:
                site_section = next(iter(sites.keys()))
            else:
                raise RuntimeError("no or more sites, please specify --site or similar")
        self.site = config.whole_data.get("sites", {})[site_section]

    @property
    def site_dir(self):
        return Path(self.config.project_dir) / self.config["site_dir"]

    @property
    def python(self):
        if self.config.running_in_docker:
            return "python3"
        return self.config.whole_data["config"]["python"]

    def call_pdm(self, *args, **kwargs):
        pdm_binary = self.config.get("pdm_binary", "pdm")
        return run_cmdline(
            pdm_binary,
            *args,
            cwd=self.site_dir,
            environ={"PDM_IGNORE_ACTIVE_VENV": "1"},
            **kwargs,
        )

    @property
    def virtualenv(self):
        return Path(os.environ.get("INVENIO_VENV", self.site_dir / ".venv"))

    @property
    def invenio_instance_path(self):
        return Path(
            os.environ.get(
                "INVENIO_INSTANCE_PATH", self.virtualenv / "var" / "instance"
            )
        )

    def call_pip(self, *args, **kwargs):
        return run_cmdline(
            self.virtualenv / "bin" / "pip",
            *args,
            **{
                "cwd": self.site_dir,
                **kwargs,
            },
        )

    def call_invenio(self, *args, **kwargs):
        return run_cmdline(
            self.virtualenv / "bin" / "invenio",
            *args,
            **{
                "cwd": self.site_dir,
                **kwargs,
            },
        )

    def get_site_local_packages(self):
        models = [
            model_name
            for model_name, model_section in self.config.whole_data.get(
                "models", {}
            ).items()
            if self.config.section in model_section.get("sites")
        ]
        uis = [
            ui_name
            for ui_name, ui_section in self.config.whole_data.get("ui", {}).items()
            if self.config.section in ui_section.get("sites")
        ]
        local_packages = [
            local_name
            for local_name, local_section in self.config.whole_data.get(
                "local", {}
            ).items()
            if self.config.section in local_section.get("sites")
        ]
        return models, uis, local_packages
