from pathlib import Path

import click

from oarepo_cli.actions.initialize import initialize_wizard
from oarepo_cli.cli.utils import print_banner
from oarepo_cli.config import MonorepoConfig


@click.command()
@click.argument(
    "project_dir", type=click.Path(exists=False, file_okay=False), required=True
)
def run(project_dir):
    project_dir = Path(project_dir).absolute()
    oarepo_yaml_file = project_dir / "oarepo.yaml"

    cfg = MonorepoConfig(oarepo_yaml_file)

    if project_dir.exists():
        if oarepo_yaml_file.exists():
            cfg.load()
        # else:
        #     sys.exit("Please select a non-existent directory")

    cfg["project_dir"] = str(project_dir)

    print_banner()

    initialize_wizard.run(cfg)


if __name__ == "__main__":
    run()
