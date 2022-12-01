from __future__ import annotations

from oarepo_cli.config import Config

from .steps import WizardStep


class Wizard:
    def __init__(self, *steps: WizardStep):
        self.steps = steps

    def run(self, data: Config):
        for step in self.steps:
            if step.should_run(data):
                step.run(data)
        self.after_run(data)

    def after_run(self, data):
        pass
