import click as click

from .add.cli import add_model
from .compile import compile_model
from .install import install_model
from .list import list_models


@click.group(
    help="Model-related tools (add model, compile, install, load and dump data)"
)
def model():
    pass


model.add_command(add_model)
model.add_command(compile_model)
model.add_command(install_model)
model.add_command(list_models)
