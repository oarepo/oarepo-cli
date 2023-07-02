from oarepo_cli.upgrade.steps.upgrade_docker_nrp import UpgradeDockerNRPStep
from oarepo_cli.upgrade.steps.upgrade_nrp import UpgradeNRPStep
from oarepo_cli.upgrade.steps.upgrade_site import UpgradeSiteStep
from oarepo_cli.wizard import Wizard
from oarepo_cli.wizard.docker import DockerRunner


class UpgradeWizard(Wizard):
    def __init__(self, runner: DockerRunner, sites=None, site=None):
        upgrade_sites_steps = []
        for s in sites:
            if site and s != site:
                continue
            upgrade_sites_steps.extend(
                runner.wrap_docker_steps(
                    UpgradeDockerNRPStep(), UpgradeSiteStep(s), site=s
                )
            )

        super().__init__(
            # upgrade nrp tooling outside of docker
            UpgradeNRPStep(),
            *upgrade_sites_steps
        )
