from __future__ import annotations

from typing import Callable, Dict, Union, List

from .steps import WizardStep
from . import WizardBase


class Wizard(WizardBase):
    def __init__(self, *steps: WizardStep):
        super().__init__(steps)
        self._data = None
        self.no_input = False
        self.silent = False
        self.verbose = False

    def should_run(self):
        return super().should_run()

    @property
    def data(self):
        return self._data

    def run_wizard(self, data, *, no_input=False, silent=False, single_step=None, verbose=False):
        self._data = data
        self.no_input = no_input
        self.silent = silent
        self.verbose = verbose
        super().run(single_step=single_step)
        if not single_step:
            self.after_run()

    def after_run(self):
        pass

    def list_steps(self):
        for s in self.steps:
            print(s.name)
