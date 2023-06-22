from __future__ import annotations

from . import WizardBase
from .steps import WizardStep


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

    def run_wizard(
        self, data, *, no_input=False, silent=False, selected_steps=None, verbose=False
    ):
        self._data = data
        self.no_input = no_input
        self.silent = silent
        self.verbose = verbose
        super().run(selected_steps=selected_steps)
        if not selected_steps:
            self.after_run()

    def after_run(self):
        pass

    def list_steps(self):
        for s in self.steps:
            print(s.name)
