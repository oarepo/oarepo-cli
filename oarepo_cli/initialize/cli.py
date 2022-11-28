from pathlib import Path

import click

from oarepo_cli.config import MonorepoConfig

from ..utils import print_banner
from .wizard import initialize_wizard


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
