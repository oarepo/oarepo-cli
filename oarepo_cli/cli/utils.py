import pyfiglet
from colorama import Fore, Style

from oarepo_cli.ui.utils import slow_print


def print_banner():
    intro_string = "\n".join(
        ["        " + x for x in pyfiglet.figlet_format("O A R e p o", font="slant", width=120).split('\n')])
    slow_print(f"\n\n\n{Fore.GREEN}{intro_string}{Style.RESET_ALL}")
