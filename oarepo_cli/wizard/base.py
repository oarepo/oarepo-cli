from __future__ import annotations

import sys
from typing import List, Tuple


class WizardBase:
    steps: List["WizardBase"] = []
    parent: "WizardBase" = None

    @property
    def name(self):
        return type(self).__name__

    @property
    def root(self):
        n = self
        while n.parent:
            n = n.parent
        return n

    @property
    def data(self):
        if self.root == self:
            raise RuntimeError(
                "Parent not initialized, should not access data at this time!"
            )
        return self.root.data

    def vprint(self, *args, **kwargs):
        if self.root.verbose:
            print(*args, **kwargs, file=sys.__stderr__)

    def __init__(self, steps: "Tuple[WizardBase]" = None):
        self.steps = steps or self.steps
        for step in self.steps:
            step.parent = self

    def run(self, selected_steps=None):
        steps = self.steps
        self.vprint(f"{self.name} running steps")
        for stepidx, step in enumerate(steps):
            if selected_steps and step.name not in selected_steps:
                continue
            self.vprint(f"Checking if step {step.name} should be run")
            should_run = step.should_run()
            if should_run is False:
                self.vprint(f"   No, skipping")
                continue
            if should_run is None:
                # only if one of the subsequent steps should run
                for subsequent in steps[stepidx + 1 :]:
                    subsequent_should_run = subsequent.should_run()
                    if subsequent_should_run is not None:
                        should_run = subsequent_should_run
                        break
                if should_run is False:
                    continue
            self.vprint(f"Calling step {step.name}")
            step.run()
            self.data.save()

    def should_run(self):
        if self.steps:
            for step in self.steps:
                if isinstance(step, str):
                    getattr(self, step)()
                should_run = step.should_run()
                if should_run:
                    return True
            return False
