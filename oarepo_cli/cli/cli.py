import click

from oarepo_cli.cli.initialize import initialize
from oarepo_cli.cli.model import model
from oarepo_cli.cli.run import run_server
from oarepo_cli.cli.site import site
from oarepo_cli.cli.ui import ui
from oarepo_cli.cli.upgrade import upgrade
from oarepo_cli.cli.develop_docker import docker_develop
from oarepo_cli.cli.develop import develop
from oarepo_cli.cli.watch import docker_watch


@click.group()
def run(*args, **kwargs):
    pass


run.add_command(initialize)
run.add_command(site)
run.add_command(model)
run.add_command(ui)
run.add_command(run_server)
run.add_command(upgrade)
run.add_command(docker_develop)
run.add_command(develop)
run.add_command(docker_watch)

if __name__ == "__main__":
    run()
