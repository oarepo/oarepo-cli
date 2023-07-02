import shutil
from pathlib import Path
from typing import List

import click as click
import yaml

from oarepo_cli.utils import commit_git, with_config

from ..model_support import ModelSupport
from .wizard import AddModelWizard


@click.command(
    name="add",
    help="""
Generate a new model. Required arguments:
    <name>   ... name of the model, can contain [a-z] and dash (-)""",
)
@click.argument("name", required=True)
@click.option(
    "--use",
    multiple=True,
    help="""
Use this option to merge your code into the generated model.

Syntax: --use <custom_model_file_relative_to_cwd>
or      --use <custom_model_file_relative_to_cwd>:<jsonpath>

The file will be copied to the destination and referenced from 
the generated model file. If no path is specified, it will be 
referenced from the root of the file, with path the reference 
will be put there. Only '/' is supported in the json path.
""",
)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def add_model(
    cfg=None,
    use=None,
    step=None,
    no_input=False,
    silent=False,
    verbose=False,
    steps=False,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-model-add-{cfg.section}",
        f"Committed automatically before model {cfg.section} has been added",
    )
    cfg["model_dir"] = f"models/{cfg.section}"

    wizard = AddModelWizard()
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, selected_steps=step, no_input=no_input, silent=silent, verbose=verbose
    )
    model_support = ModelSupport(cfg)

    merge_extra_sources(model_support, use or [])
    commit_git(
        cfg.project_dir,
        f"after-model-add-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been added",
    )


def merge_extra_sources(model_support: ModelSupport, sources: List[str]):
    for d in sources:
        d = d.split(":")
        if len(d) < 2:
            filepath = d[0]
            jsonpath = "/"
        else:
            filepath, jsonpath = d

        extra_file_name = Path(filepath).name
        model_dir = model_support.model_dir
        model_file_path = model_dir / "model.yaml"

        shutil.copy(filepath, model_dir / extra_file_name)

        with model_file_path.open() as f:
            json_data = yaml.safe_load(f)

        add_oarepo_use(json_data, jsonpath.split("/"), f"./{extra_file_name}")

        with model_file_path.open("wt") as f:
            yaml.safe_dump(json_data, f)


def add_oarepo_use(d, path, value):
    for p in path:
        if not p:
            continue
        if p not in d:
            d[p] = {}
        d = d[p]

    if "use" in d:
        if not isinstance(d["use"], list):
            d["use"] = [d["use"]]
    else:
        d["use"] = []
    d["use"].append(value)
