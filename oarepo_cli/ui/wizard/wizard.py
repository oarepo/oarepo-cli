from __future__ import annotations

from oarepo_cli.config import Config

from .steps import WizardStep


class Wizard:
    def __init__(self, *steps: WizardStep):
        self.steps = steps

    def run(self, data: Config):
        for step in self.steps:
            step.run(data)
