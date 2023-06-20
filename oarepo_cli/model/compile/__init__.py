import click as click

from oarepo_cli.model.compile.wizard import CompileModelWizard
from oarepo_cli.utils import commit_git, with_config


@click.command(
    name="compile",
    help="""
Compile model yaml file to invenio sources. Required arguments:
    <name>   ... name of the already existing model
""",
)
@click.argument("name", required=True)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def compile_model(
    cfg=None,
    no_input=False,
    silent=False,
    step=None,
    steps=False,
    verbose=False,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-model-compile-{cfg.section}",
        f"Committed automatically before model {cfg.section} has been compiled",
    )
    wizard = CompileModelWizard()
    if steps:
        wizard.list_steps()
        return

    wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, single_step=step, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-model-compile-{cfg.section}",
        f"Committed automatically after model {cfg.section} has been compiled",
    )