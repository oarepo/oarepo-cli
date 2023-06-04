import click as click

from oarepo_cli.old_cli.utils import with_config
from oarepo_cli.utils import commit_git

from .wizard import AddModelWizard


@click.command(
    name="add",
    help="""
Generate a new model. Required arguments:
    <name>   ... name of the model, can contain [a-z] and dash (-)""",
)
@click.argument("name", required=True)
# @click.option(
#     "--merge",
#     multiple=True,
#     help="""
# Use this option to merge your code into the generated model.
#
# --merge my_dir              will merge my_dir with the generated sources
#
# --merge my_dir=gen_subdir   will merge my_dir into the subdir(relative path to models/<model>)
#
# --merge my_file=<rel_path_to_file>   will merge single file
#
# Normally, user file is merged at the end of the generated file - that is, the content of generated file goes first (includes, classes, arrays).
#
# Use '-' before the dir/file to reverse the order - the content of your file will be prepended to an existing file
# Use '!' before the dir/file to copy the file to destination without merging it
# """,
# )
@with_config(config_section=lambda name, **kwargs: ["models", name])
def add_model(
    cfg=None,
    merge=None,
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
    # if merge:
    #     venv_dir: Path = cfg.project_dir / ".venv" / "oarepo-model-builder"
    #     venv_dir = venv_dir.absolute()
    #     if not venv_dir.exists():
    #         venv_dir.parent.mkdir(parents=True, exist_ok=True)
    #         venv.main([str(venv_dir)])
    #
    #         pip_install(
    #             venv_dir / "bin" / "pip",
    #             "OAREPO_MODEL_BUILDER_VERSION",
    #             "oarepo-model-builder==3.*",
    #             "https://github.com/oarepo/oarepo-model-builder",
    #         )

    wizard = AddModelWizard()
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, single_step=step, no_input=no_input, silent=silent, verbose=verbose
    )

    # if merge:
    #     for merge_def in merge:
    #         opts = []
    #         merge_def = merge_def.split("=", maxsplit=1)
    #
    #         merge_source: Path = merge_def[0]
    #         if merge_source[0] == "-":
    #             merge_source = merge_source[1:]
    #             opts.append("--destination-first")
    #         if merge_source[0] == "!":
    #             merge_source = merge_source[1:]
    #             opts.append("--overwrite")
    #
    #         merge_target: Path = cfg.project_dir
    #         for p in cfg.section_path:
    #             merge_target = merge_target / p
    #         if len(merge_def) == 2:
    #             merge_target = merge_target.joinpath(merge_def[1])
    #
    #         subprocess.call(
    #             [
    #                 venv_dir / "bin" / "oarepo-merge",
    #                 Path(merge_source).absolute(),
    #                 Path(merge_target).absolute(),
    #                 *opts,
    #             ]
    #         )
    commit_git(
        cfg.project_dir,
        f"after-model-add-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been added",
    )
