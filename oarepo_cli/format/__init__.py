import click

from oarepo_cli.format.wizard import FormatWizard
from oarepo_cli.utils import commit_git, to_python_name, with_config
from oarepo_cli.wizard.docker import DockerRunner


@click.command(
    name="format",
    help="""Format all source files inside the project""",
)
@with_config()
def format_sources(
    cfg=None,
    no_input=False,
    silent=False,
    step=None,
    verbose=False,
    steps=False,
    **kwargs,
):
    commit_git(
        cfg.project_dir,
        f"before-file-format-{cfg.section}",
        f"Committed automatically before file formatting",
    )

    runner = DockerRunner(cfg, no_input)
    initialize_wizard = FormatWizard(runner)
    if steps:
        initialize_wizard.list_steps()
        return

    initialize_wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, single_step=step, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-file-format-{cfg.section}",
        f"Committed automatically after files have been formatted",
    )
