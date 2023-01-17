import click as click

from oarepo_cli.cli.model.utils import ModelWizardStep
from oarepo_cli.cli.utils import with_config
from oarepo_cli.ui.wizard import Wizard


@click.command(
    name="load",
    help="""
Import (sample) data. Required arguments:
    <name>       ... name of the already existing model
    <data-path>  ... path to the data. If not filled, sample data will be used
    """,
)
@click.argument("name", required=False)
@click.argument(
    "data-path", required=False, type=click.Path(file_okay=True, dir_okay=False)
)
@with_config(config_section=lambda name, **kwargs: ["models", name])
def load_data(cfg=None, data_path=None, *args, **kwargs):
    if not data_path:
        data_path = cfg.project_dir / cfg["model_dir"] / "data" / "sample_data.yaml"
        cfg["data_path"] = "data" / "sample_data.yaml"
    else:
        cfg["data_path"] = data_path

    w = Wizard(ImportDataWizardStep())
    w.run(cfg)


class ImportDataWizardStep(ModelWizardStep):
    def after_run(self):
        data_path = self.model_dir.join(self.data["data_path"])
        self.invenio_command(self.model_name, "load", data_path)
