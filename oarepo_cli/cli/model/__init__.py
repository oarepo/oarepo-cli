import click as click

from .add import add_model
from .compile import compile_model
from .install import install_model


@click.group()
def model():
    pass


model.add_command(add_model)
model.add_command(compile_model)
model.add_command(install_model)
