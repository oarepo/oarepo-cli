from __future__ import annotations

import abc
import copy
from typing import Any, Callable, Dict, List, Union

from colorama import Fore, Style

from ...config import Config
from ..input import Input
from ..radio import Radio
from ..utils import slow_print
from .validation import required as required_validation


class WizardBase(abc.ABC):
    steps: "List[Union[WizardStep, Callable[[Dict], None], str]]" = []
    data: Dict[str, Any] = None

    def __init__(
        self, steps: "List[Union[WizardStep, Callable[[Dict], None], str]]" = None
    ):
        self.steps = steps or self.steps

    def run(self, data):
        self.data = data
        steps = self.get_steps()
        for step in steps:
            step.data = data
        for stepidx, step in enumerate(steps):
            should_run = step.should_run()
            if should_run is False:
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
            step.run(data)
            data.save()

    def get_steps(self):
        return self.steps

    @abc.abstractmethod
    def should_run(self):
        if self.steps:
            steps = self.get_steps()
            for step in steps:
                if isinstance(step, str):
                    getattr(self, step)()
                should_run = step.should_run()
                if should_run:
                    return True
            return False


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
        self.data = data
        self.on_before_heading()
        if self.heading and not data.silent:
            heading = self.heading
            if callable(heading):
                heading = heading(data)
            if heading:
                slow_print(f"\n\n{Fore.BLUE}{heading}{Style.RESET_ALL}")
            print()
        self.on_after_heading()
        valid = False
        while not valid:
            widgets = self.get_widgets()
            for widget in widgets:
                widget_value = data.get(widget.name)
                if widget_value is None and widget.default:
                    if callable(widget.default):
                        widget_value = widget.default(data)
                    else:
                        widget_value = copy.deepcopy(widget.default)
                if data.no_input:
                    if widget_value is None:
                        raise ValueError(
                            f"Do not have a value for option {widget.name}, please specify it in the config"
                        )
                    if widget.value != widget_value:
                        data[widget.name] = widget_value
                    # propagate default if needed
                    continue
                widget.value = widget_value
                data[widget.name] = widget.run()
            valid = True
            validate_functions = self.get_validate_functions()
            for v in validate_functions:
                res = v(data)
                if res is True or res is None:
                    continue
                print(f"{Fore.RED}Error: {res}{Style.RESET_ALL}")
                valid = False
            if not valid and data.no_input:
                raise ValueError(f"Config not valid and not running interactively")
        super().run(data)
        if self.pause and not data.no_input:
            input(f"Press enter to continue ...")
        self.after_run()

    def on_before_heading(self):
        pass

    def on_after_heading(self):
        pass

    def get_widgets(self):
        return self.widgets

    def get_validate_functions(self):
        return self.validate_functions

    def on_after_steps(self):
        pass

    def after_run(self):
        pass


class InputWizardStep(WizardStep):
    def __init__(
        self,
        key,
        heading=None,
        required=True,
        default=None,
        prompt=None,
        force_run=False,
    ):
        super().__init__(
            Input(key, default=default, prompt=prompt),
            heading=heading,
            validate=[required_validation(key)] if required else [],
        )
        self.key = key
        self.force_run = force_run

    def should_run(self):
        return self.force_run or self.key not in self.data


class StaticWizardStep(WizardStep):
    def __init__(self, heading, **kwargs):
        super().__init__(heading=heading, **kwargs)

    def should_run(self):
        # do not know - should run only if one of the subsequent steps should run
        return None


class RadioWizardStep(WizardStep):
    def __init__(self, key, heading=None, options=None, default=None, force_run=False):
        super().__init__(Radio(key, default=default, options=options), heading=heading)
        self.key = key
        self.force_run = force_run

    def should_run(self):
        return self.force_run or self.key not in self.data
