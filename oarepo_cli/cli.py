import click

from oarepo_cli.build_command.cli import build_command
from oarepo_cli.develop.cli import develop_command
from oarepo_cli.format.cli import format_sources_command
from oarepo_cli.initialize.cli import initialize_command
from oarepo_cli.invenio.cli import invenio_command
from oarepo_cli.kill import kill_command
from oarepo_cli.local import local_commands
from oarepo_cli.model import model_commands
from oarepo_cli.oarepo.cli import oarepo_command
from oarepo_cli.run.cli import run_server_command
from oarepo_cli.site import site_commands
from oarepo_cli.ui import ui_commands
from oarepo_cli.upgrade.cli import upgrade_command
from oarepo_cli.watch.cli import watch_command


@click.group()
def run(*args, **kwargs):
    pass


run.add_command(initialize_command)
run.add_command(site_commands)
run.add_command(model_commands)
run.add_command(local_commands)
run.add_command(ui_commands)
run.add_command(run_server_command)
run.add_command(upgrade_command)
run.add_command(develop_command)
run.add_command(watch_command)
run.add_command(format_sources_command)
run.add_command(kill_command)
run.add_command(build_command)
run.add_command(invenio_command)
run.add_command(oarepo_command)

if __name__ == "__main__":
    run()
