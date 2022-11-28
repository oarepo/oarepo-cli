import click

from oarepo_cli.cli.model import model


@click.group()
def run(*args, **kwargs):
    pass


run.add_command(model)

if __name__ == "__main__":
    run()
