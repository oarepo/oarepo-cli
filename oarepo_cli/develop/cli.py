import errno
import os
import time

import click as click

from oarepo_cli.develop.config import CONTROL_PIPE
from oarepo_cli.develop.wizard import WebpackDevelopWizard, ViteDevelopWizard
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import with_config
from oarepo_cli.wizard.docker import DockerRunner


@click.command(
    name="develop",
    hidden=True,
    help="""Use this command to start development server (either in docker or in userspace).
    You can pass your custom libraries, which will be prepended to python path as editables. 
    The list of libraries must be in the form <library-name>=<library-path>
    """,
)
@click.option("--site", required=False)
@click.option("--command", required=False, hidden=True)
@click.option("--vite/--no-vite")
@click.option(
    "--fast/--no-fast", help="Do not check dependencies nor build repository in advance"
)
@click.option("--clean/--no-clean", help="Clean all dependencies and rebuild")
@click.option(
    "--upgrade/--no-upgrade", help="Upgrade python dependencies when build starts"
)
@click.argument("libraries", nargs=-1)
@with_config()
def develop_command(
    cfg,
    no_input=False,
    silent=False,
    step=None,
    verbose=False,
    steps=False,
    site=None,
    command=None,
    vite=None,
    libraries=None,
    fast=False,
    clean=False,
    upgrade=False,
    **kwargs,
):
    if command:
        # there is a CONTROL_PIPE pipe, send command to it and quit
        send_command(command)
        return

    site_support = SiteSupport(cfg, site)

    if clean:
        site_support.clean()
        fast = False
    if upgrade:
        site_support.remove_dependencies()
        fast = False

    libraries = dict(x.split("=", maxsplit=1) for x in libraries)

    runner = DockerRunner(cfg, no_input)
    if vite:
        develop_wizard = ViteDevelopWizard(
            runner, site_support=site_support, fast=fast, libraries=libraries
        )
    else:
        develop_wizard = WebpackDevelopWizard(
            runner, site_support=site_support, fast=fast
        )

    if steps:
        develop_wizard.list_steps()
        return

    develop_wizard.run_wizard(
        cfg, no_input=no_input, silent=silent, selected_steps=step, verbose=verbose
    )


def send_command(command):
    # make sure CONTROL_PIPE is a pipe
    try:
        os.mkfifo(CONTROL_PIPE)
    except OSError as oe:
        if oe.errno != errno.EEXIST:
            raise

    with open(CONTROL_PIPE, "w") as f:
        f.write(command + "\n")
        f.flush()
        time.sleep(2)
