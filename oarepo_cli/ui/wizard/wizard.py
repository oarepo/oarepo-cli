from __future__ import annotations

from typing import Callable, Dict, Union

from oarepo_cli.config import Config

from .steps import WizardStep


class Wizard:
    def __init__(self, *steps: Union[WizardStep, Callable[[Dict], None]]):
        self.steps = steps

    def run(self, data: Config):
        for step in self.steps:
            if callable(step):
                step(data)
            elif step.should_run(data):
                step.run(data)
        self.after_run(data)

    def after_run(self, data):
        pass
