import click

from oarepo_cli.dependencies import dependencies
from oarepo_cli.develop.cli import develop
from oarepo_cli.format.cli import format_sources
from oarepo_cli.initialize.cli import initialize
from oarepo_cli.local import local
from oarepo_cli.model import model
from oarepo_cli.run.cli import run_server
from oarepo_cli.site import site
from oarepo_cli.ui import ui
from oarepo_cli.upgrade import upgrade
from oarepo_cli.watch import docker_watch
from oarepo_cli.kill import kill


@click.group()
def run(*args, **kwargs):
    pass


run.add_command(initialize)
run.add_command(site)
run.add_command(model)
run.add_command(local)
run.add_command(ui)
run.add_command(run_server)
run.add_command(upgrade)
run.add_command(develop)
run.add_command(docker_watch)
run.add_command(dependencies)
run.add_command(format_sources)
run.add_command(kill)

if __name__ == "__main__":
    run()
