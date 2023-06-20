import click

from oarepo_cli.dependencies import dependencies
from oarepo_cli.develop import develop
from oarepo_cli.docker_develop import docker_develop
from oarepo_cli.initialize import initialize
from oarepo_cli.local import local
from oarepo_cli.model import model
from oarepo_cli.run import run_server
from oarepo_cli.site import site
from oarepo_cli.ui import ui
from oarepo_cli.upgrade import upgrade
from oarepo_cli.watch import docker_watch


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
run.add_command(docker_develop)
run.add_command(develop)
run.add_command(docker_watch)
run.add_command(dependencies)

if __name__ == "__main__":
    run()