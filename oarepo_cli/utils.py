import os
import signal
import subprocess
import sys
from pathlib import Path

import pyfiglet
from colorama import Fore, Style

from oarepo_cli.ui.utils import slow_print


def print_banner():
    intro_string = "\n".join(
        [
            "        " + x
            for x in pyfiglet.figlet_format(
                "O A R e p o", font="slant", width=120
            ).split("\n")
        ]
    )
    slow_print(f"\n\n\n{Fore.GREEN}{intro_string}{Style.RESET_ALL}")


def run_cmdline(*cmdline, cwd=".", environ=None):
    env = os.environ.copy()
    env.update(environ or {})
    cwd = Path(cwd).absolute()
    cmdline = [str(x) for x in cmdline]
    print(
        f"{Fore.BLUE}Running {Style.RESET_ALL} {' '.join(cmdline)}", file=sys.__stderr__
    )
    print(f"{Fore.BLUE}    inside {Style.RESET_ALL} {cwd}", file=sys.__stderr__)
    ret = subprocess.call(cmdline, cwd=cwd, env=env)
    if ret:
        print(f"Error running {' '.join(cmdline)}", file=sys.__stderr__)
        sys.exit(ret)
    print(
        f"{Fore.GREEN}Finished running {Style.RESET_ALL} {' '.join(cmdline)}",
        file=sys.__stderr__,
    )
    print(f"{Fore.GREEN}    inside {Style.RESET_ALL} {cwd}", file=sys.__stderr__)


def find_oarepo_project(dirname, raises=False):
    dirname = Path(dirname).absolute()
    orig_dirname = dirname
    for _ in range(4):
        if (dirname / "oarepo.yaml").exists():
            return dirname
        dirname = dirname.parent
    if raises:
        raise Exception(
            f"Not part of OARepo project: directory {orig_dirname} "
            f"or its 4 ancestors do not contain oarepo.yaml file"
        )
    return
