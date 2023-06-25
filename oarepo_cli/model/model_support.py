from pathlib import Path

from oarepo_cli.config import MonorepoConfig


class ModelSupport:
    def __init__(self, config: MonorepoConfig, model_section=None):
        self.config = config
        models = config.whole_data.get("models", {})

        if config.section_path[0] == "models":
            self.model = config
            self.model_name = config.section_path[-1]
            return
        elif not model_section:
            if len(models) == 1:
                model_section = next(iter(models.keys()))
            else:
                raise RuntimeError(
                    "none or more models, please specify the model on commandline"
                )
        self.model = models[model_section]
        self.model_name = model_section

    @property
    def model_dir(self):
        return Path(self.config.project_dir) / self.config["model_dir"]
