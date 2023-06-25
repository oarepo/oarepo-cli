from oarepo_cli.config import MonorepoConfig
from oarepo_cli.wizard import Wizard
from .add.steps.compile_gui import CompileGUIStep

from .add.steps.install_invenio import InstallInvenioStep
from .add.steps.resolve_dependencies import ResolveDependenciesStep
from .site_support import SiteSupport


def update_and_install_site(
    config: MonorepoConfig, site_name: str, silent=False, verbose=False, clean=False, compile_gui=False
):
    if verbose:
        print(f"Installing {site_name}")

    assert site_name in config.whole_data["sites"]
    site_config = config.clone(["sites", site_name])
    wizard = Wizard(
        ResolveDependenciesStep(),
        InstallInvenioStep(clean=clean),
        *([CompileGUIStep()] if compile_gui else [])
    )
    wizard.run_wizard(site_config, no_input=True, silent=silent, verbose=verbose)


def remove_from_site_venv(
    config: MonorepoConfig, site_name: str, silent=False, verbose=False
):
    site = SiteSupport(config, site_name)
    site.call_pip("uninstall", site.site_name)
