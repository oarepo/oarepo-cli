import os

from oarepo_cli.upgrade.steps.upgrade_nrp import upgrade_venv
from oarepo_cli.wizard import WizardStep


class UpgradeDockerNRPStep(WizardStep):
    def should_run(self):
        return self.data.running_in_docker

    def after_run(self):
        upgrade_venv(os.environ["NRP_VENV"])
