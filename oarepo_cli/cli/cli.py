import click

from oarepo_cli.cli.model import model
from oarepo_cli.cli.run import run_server
from oarepo_cli.cli.ui import ui


@click.group()
def run(*args, **kwargs):
    pass


run.add_command(model)
run.add_command(ui)
run.add_command(run_server)

if __name__ == "__main__":
    run()
