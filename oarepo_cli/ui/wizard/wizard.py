from __future__ import annotations

from typing import Callable, Dict, Union

from .steps import WizardBase, WizardStep


class Wizard(WizardBase):
    def __init__(self, *steps: Union[WizardStep, Callable[[Dict], None], str]):
        super().__init__(steps)

    def should_run(self, data):
        return super().should_run(data)

    def run(self, data):
        super().run(data)
        self.after_run()

    def after_run(self):
        pass
