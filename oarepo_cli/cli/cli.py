import click

from oarepo_cli.cli.model import model
from oarepo_cli.cli.run import run_server


@click.group()
def run(*args, **kwargs):
    pass


run.add_command(model)
run.add_command(run_server)

if __name__ == "__main__":
    run()
