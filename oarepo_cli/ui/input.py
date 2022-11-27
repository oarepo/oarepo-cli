from colorama import Fore, Style

try:
    import gnureadline as readline
except ImportError:
    import readline

from oarepo_cli.ui.widget import Widget


class Input(Widget):
    def run(self):
        def hook():
            readline.insert_text(self.value or "")
            readline.redisplay()

        readline.set_pre_input_hook(hook)

        try:
            line = input(f"{Fore.BLUE}Enter value: {Style.RESET_ALL}")
        finally:
            readline.set_pre_input_hook()
        self.value = line
        return line
