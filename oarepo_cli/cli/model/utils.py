import os
from pathlib import Path

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import find_oarepo_project


def load_model_repo(model_name, project_dir):
    project_dir = find_oarepo_project(project_dir)
    if not model_name:
        model_name = Path(os.getcwd()).name
    oarepo_yaml_file = project_dir / "oarepo.yaml"
    cfg = MonorepoConfig(oarepo_yaml_file, section=["models", model_name])
    cfg.load()
    return cfg, project_dir
