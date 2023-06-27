from __future__ import annotations

import readline

from colorama import Fore, Style

from .base import WizardBase


class WizardStep(WizardBase):
    heading = ""
    pause = None

    def __init__(
        self,
        *steps: "WizardBase",
        heading=None,
        pause=False,
        **kwargs,
    ):
        super().__init__(steps)
        self.heading = heading or self.heading
        self.pause = pause or self.pause

    def run(self, selected_steps=None):
        if not self.on_before_run():
            return
        self.on_before_heading()
        self._print_heading()
        self.on_after_heading()
        super().run(selected_steps=selected_steps)
        if self.pause and not self.root.no_input:
            input(f"Press enter to continue ...")
        self.after_run()

    def _print_heading(self):
        if self.heading and not self.root.silent:
            heading = self.heading
            if callable(heading):
                heading = heading(self.data)
            if heading:
                print(f"\n\n{Fore.BLUE}{heading.strip()}{Style.RESET_ALL}")
            print()

    def on_before_run(self):
        return True

    def on_before_heading(self):
        pass

    def on_after_heading(self):
        pass

    def on_after_steps(self):
        pass

    def after_run(self):
        pass


class InputStep(WizardStep):
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
            heading=heading,
        )
        self.key = key
        self.force_run = force_run
        self._default = default
        self.prompt = prompt
        self.required = required

    @property
    def default(self):
        if callable(self._default):
            return self._default(self.data)
        return self._default

    def run(self, **kwargs):
        value = self.data.get(self.key, self.default)

        while True:
            try:
                prompt = self.prompt or "Enter value"
                if self.default:
                    prompt += f" [{self.default}]"
                line = input(f"{Fore.BLUE}{prompt}: {Style.RESET_ALL}")
                line = line.strip() or value
                if line or not self.required:
                    self.data[self.key] = line
                    return
            finally:
                readline.set_pre_input_hook()

    def should_run(self):
        return self.force_run or self.key not in self.data


class StaticStep(WizardStep):
    def __init__(self, heading, **kwargs):
        super().__init__(heading=heading, **kwargs)

    def should_run(self):
        # do not know - should run only if one of the subsequent steps should run
        return None


class RadioStep(WizardStep):
    def __init__(self, key, heading=None, options=None, default=None, force_run=False):
        super().__init__(heading=heading)
        self.key = key
        self.force_run = force_run
        self._default = default
        self.options = options

    @property
    def default(self):
        if callable(self._default):
            return self._default(self.data)
        return self._default

    def run(self, **kwargs):
        super().run(**kwargs)
        value = self.data.get(self.key, self.default)

        options = self.options
        if callable(options):
            options = options()

        displayed = [
            (str(idx + 1), key, label)
            for idx, (key, label) in enumerate(options.items())
        ]
        print()
        for d in displayed:
            print(f"{Fore.YELLOW}{d[0]}{Style.RESET_ALL}) {d[2]}")

        option = None
        for d in displayed:
            if d[1] == value:
                option = d[0]
                break
        if option:
            prompt = f"Your choice [{option}]: "
        else:
            prompt = "Your choice: "

        while True:
            print()
            value = input(prompt).strip() or option
            for d in displayed:
                if d[0] == value:
                    self.data[self.key] = d[1]
                    return
            print(
                f"{Fore.RED}Bad option: select one of the options above{Style.RESET_ALL}"
            )

    def should_run(self):
        return (not self.data.no_input and self.force_run) or self.key not in self.data
