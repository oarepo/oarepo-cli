import click as click

from .add.cli import add_model
from .compile.cli import compile_model
from .install.cli import install_model
from .list import list_models
from .uninstall.cli import uninstall_model


@click.group(
    help="Model-related tools (add model, compile, install, load and dump data)",
    name="model",
)
def model_commands():
    pass


model_commands.add_command(add_model)
model_commands.add_command(compile_model)
model_commands.add_command(install_model)
model_commands.add_command(uninstall_model)
model_commands.add_command(list_models)
