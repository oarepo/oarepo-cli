from oarepo_cli.config import MonorepoConfig
from oarepo_cli.wizard import Wizard

from ..utils import run_cmdline
from .add.steps.install_invenio import InstallInvenioStep
from .add.steps.resolve_dependencies import ResolveDependenciesStep


def update_and_install_site(
    config: MonorepoConfig, site_name: str, silent=False, verbose=False
):
    if verbose:
        print(f"Installing {site_name}")
    assert site_name in config.whole_data["sites"]
    site_config = MonorepoConfig(config.path, section=["sites", site_name])
    site_config.load()
    wizard = Wizard(ResolveDependenciesStep(), InstallInvenioStep())
    wizard.run_wizard(site_config, no_input=True, silent=silent, verbose=verbose)


def remove_from_site_venv(
    config: MonorepoConfig, site_name: str, silent=False, verbose=False
):
    assert site_name in config.whole_data["sites"]
    site_config = MonorepoConfig(config.path, section=["sites", site_name])
    site_config.load()

    pip_cmd = (
        site_config.project_dir / site_config["site_dir"] / ".venv" / "bin" / "pip"
    )

    run_cmdline(pip_cmd, "uninstall", config.section_path[-1])
