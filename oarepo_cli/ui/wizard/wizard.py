from __future__ import annotations

from typing import Callable, Dict, Union

from oarepo_cli.config import Config

from .steps import WizardStep, WizardBase


class Wizard(WizardBase):
    def __init__(self, *steps: Union[WizardStep, Callable[[Dict], None], str]):
        super().__init__(steps)

    def run(self, data: Config):
        super().run(data)
        self.after_run(data)

    def after_run(self, data):
        pass
