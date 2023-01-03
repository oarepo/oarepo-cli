from __future__ import annotations

import copy

from typing import List, Union, Callable, Dict
from colorama import Fore, Style

from ...config import Config
from ..input import Input
from ..radio import Radio
from ..utils import slow_print
from .validation import required as required_validation
import abc

class WizardBase(abc.ABC):
    steps: "List[Union[WizardStep, Callable[[Dict], None], str]]" = []

    def __init__(self, steps: "List[Union[WizardStep, Callable[[Dict], None], str]]" = None):
        self.steps = steps or self.steps

    def run(self, data):
        steps = self.get_steps(data)
        for step in steps:
            if isinstance(step, str):
                getattr(self, step)(data)
            elif callable(step):
                step(data)
            else:
                step.run(data)

    def get_steps(self, data):
        return self.steps

    @abc.abstractmethod
    def should_run(self, data):
        raise Exception('Implement this !!!')


class WizardStep(WizardBase):
    widgets = ()
    validate_functions = ()
    heading = ""
    pause = None

    def __init__(
            self,
            *widgets,
            validate=None,
            heading=None,
            pause=False,
            steps=None,
            **kwargs,
    ):
        super().__init__(steps)
        self.widgets = tuple(widgets or self.widgets)
        if not validate:
            validate = []
        elif not isinstance(validate, (list, tuple)):
            validate = tuple(validate)
        self.validate_functions = tuple(validate or self.validate_functions)
        self.heading = heading or self.heading
        self.pause = pause or self.pause

    def run(self, data: Config):
        if not self.should_run(data):
            return
        self.on_before_heading(data)
        if self.heading:
            heading = self.heading
            if callable(heading):
                heading = heading(data)
            if heading:
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
        super().run(data)
        self.on_after_steps(data)
        if self.pause:
            input(f"Press enter to continue ...")
        self.after_run(data)

    def on_before_heading(self, data):
        pass

    def on_after_heading(self, data):
        pass

    def get_widgets(self, data):
        return self.widgets

    def get_validate_functions(self, data):
        return self.validate_functions

    def on_after_steps(self, data):
        pass

    def after_run(self, data):
        pass


class InputWizardStep(WizardStep):
    def __init__(self, key, heading=None, required=True, default=None, prompt=None):
        super().__init__(
            Input(key, default=default, prompt=prompt),
            heading=heading,
            validate=[required_validation(key)] if required else [],
        )


class StaticWizardStep(WizardStep):
    def __init__(self, key, heading, **kwargs):
        super().__init__(heading=heading, **kwargs)


class RadioWizardStep(WizardStep):
    def __init__(self, key, heading, options=None, default=None):
        super().__init__(Radio(key, default=default, options=options), heading=heading)
