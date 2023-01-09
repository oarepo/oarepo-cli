try:
    pass
except ImportError:
    pass

from typing import Dict

from colorama import Fore, Style

from oarepo_cli.ui.widget import Widget


class Radio(Widget):
    def __init__(self, name, options: Dict[str, str], default=None):
        super().__init__(name)
        self.options = options
        self.default = default

    def run(self):
        displayed = [
            (str(idx + 1), key, label)
            for idx, (key, label) in enumerate(self.options.items())
        ]
        print()
        for d in displayed:
            print(f"{Fore.YELLOW}{d[0]}{Style.RESET_ALL}) {d[2]}")

        value = self.value or self.default
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
                    return d[1]
            print(
                f"{Fore.RED}Bad option: select one of the options above{Style.RESET_ALL}"
            )
