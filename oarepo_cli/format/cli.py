import click

from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import commit_git, with_config
from oarepo_cli.wizard.docker import DockerRunner

from .wizard import FormatWizard


@click.command(
    name="format",
    help="""Format all source files inside the project""",
)
@with_config()
def format_sources_command(
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
    site_support = SiteSupport(cfg)

    runner = DockerRunner(cfg, no_input)
    format_wizard = FormatWizard(runner, site_support)
    if steps:
        format_wizard.list_steps()
        return

    format_wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, selected_steps=step, verbose=verbose
    )
    commit_git(
        cfg.project_dir,
        f"after-file-format-{cfg.section}",
        f"Committed automatically after files have been formatted",
    )
