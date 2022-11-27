from colorama import Fore, Style

try:
    import gnureadline as readline
except ImportError:
    import readline

from oarepo_cli.ui.widget import Widget


class Input(Widget):
    def __init__(self, name, default=None, prompt=None):
        super().__init__(name, default=default)
        self.prompt = prompt

    def run(self):
        def hook():
            readline.insert_text(self.value or "")
            readline.redisplay()

        readline.set_pre_input_hook(hook)

        try:
            prompt = self.prompt or "Enter value"
            line = input(f"{Fore.BLUE}{prompt}: {Style.RESET_ALL}")
        finally:
            readline.set_pre_input_hook()
        self.value = line
        return line
