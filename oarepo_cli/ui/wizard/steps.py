from __future__ import annotations

import copy

from colorama import Fore, Style

from ..input import Input
from .validation import required as required_validation
from ..radio import Radio
from ..utils import slow_print
from ...config import Config


class WizardStep:
    step_name = None
    steps: "WizardStep" = []

    def __init__(self, *widgets, validate=None, heading=None, pause=False, **kwargs):
        self.widgets = widgets
        if not validate:
            validate = []
        elif not isinstance(validate, (list, tuple)):
            validate = tuple(validate)
        self.validate_functions = tuple(validate)
        self.heading = heading
        self.pause = pause

    def run(self, data: Config):
        if data.is_step_ok(self.step_name):
            return
        self.on_before_heading(data)
        if self.heading:
            heading = self.heading
            if callable(heading):
                heading = heading(data)
            slow_print(f"\n\n{Fore.BLUE}{heading}{Style.RESET_ALL}")
            print()
        self.on_after_heading(data)
        valid = False
        while not valid:
            widgets = self.get_widgets(data)
            for widget in widgets:
                widget.value = data.get(widget.name)
                if widget.value is None and widget.default:
                    if callable(widget.default):
                        widget.value = widget.default(data)
                    else:
                        widget.value = copy.deepcopy(widget.default)
                data[widget.name] = widget.run()
            valid = True
            validate_functions = self.get_validate_functions(data)
            for v in validate_functions:
                res = v(data)
                if res is True or res is None:
                    continue
                print(f"{Fore.RED}Error: {res}{Style.RESET_ALL}")
                valid = False
        steps = self.get_steps(data)
        for step in steps:
            step.run(data)
        self.on_after_steps(data)
        if self.pause:
            input(f"Press enter to continue ...")
        self.after_run(data)
        data.set_step_ok(self.step_name)

    def on_before_heading(self, data):
        pass

    def on_after_heading(self, data):
        pass

    def get_widgets(self, data):
        return self.widgets

    def get_validate_functions(self, data):
        return self.validate_functions

    def get_steps(self, data):
        return self.steps

    def on_after_steps(self, data):
        pass

    def after_run(self, data):
        pass


class InputWizardStep(WizardStep):
    def __init__(self, key, heading=None, required=True, default=None, prompt=None):
        self.step_name = key
        super().__init__(
            Input(key, default=default, prompt=prompt),
            heading=heading,
            validate=[required_validation(key)] if required else [],
        )


class StaticWizardStep(WizardStep):
    def __init__(self, key, heading, **kwargs):
        self.step_name = key
        super().__init__(
            heading=heading, **kwargs
        )


class RadioWizardStep(WizardStep):
    def __init__(self, key, heading, options=None, default=None):
        self.step_name = key
        super().__init__(
            Radio(key, default=default, options=options),
            heading=heading
        )
