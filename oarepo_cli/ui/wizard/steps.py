from __future__ import annotations

import abc
import copy
from typing import Callable, Dict, List, Union

from colorama import Fore, Style

from ...config import Config
from ..input import Input
from ..radio import Radio
from ..utils import slow_print
from .validation import required as required_validation


class WizardBase(abc.ABC):
    steps: "List[Union[WizardStep, Callable[[Dict], None], str]]" = []

    def __init__(
        self, steps: "List[Union[WizardStep, Callable[[Dict], None], str]]" = None
    ):
        self.steps = steps or self.steps

    def run(self, data):
        steps = self.get_steps(data)
        for stepidx, step in enumerate(steps):
            if isinstance(step, str):
                getattr(self, step)(data)
            should_run = step.should_run(data)
            if should_run is False:
                continue
            if should_run is None:
                # only if one of the subsequent steps should run
                for subsequent in steps[stepidx + 1 :]:
                    if isinstance(subsequent, str):
                        getattr(self, subsequent)(data)
                    subsequent_should_run = subsequent.should_run(data)
                    if subsequent_should_run is not None:
                        should_run = subsequent_should_run
                        break
                if should_run is False:
                    continue
            step.run(data)
            data.save()

    def get_steps(self, data):
        return self.steps

    @abc.abstractmethod
    def should_run(self, data):
        if self.steps:
            steps = self.get_steps(data)
            for step in steps:
                if isinstance(step, str):
                    getattr(self, step)(data)
                should_run = step.should_run(data)
                if should_run:
                    return True
            return False
        raise Exception("Implement this !!!")


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
        self.key = key

    def should_run(self, data):
        return self.key not in data


class StaticWizardStep(WizardStep):
    def __init__(self, heading, **kwargs):
        super().__init__(heading=heading, **kwargs)

    def should_run(self, data):
        # do not know - should run only if one of the subsequent steps should run
        return None


class RadioWizardStep(WizardStep):
    def __init__(self, key, heading, options=None, default=None):
        super().__init__(Radio(key, default=default, options=options), heading=heading)
        self.key = key

    def should_run(self, data):
        return self.key not in data
