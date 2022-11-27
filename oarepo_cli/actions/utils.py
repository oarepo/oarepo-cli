import os
import signal
import subprocess
import sys
from pathlib import Path

from colorama import Style, Fore, Back


def run_cmdline(*cmdline, cwd=".", environ=None):
    env = os.environ.copy()
    env.update(environ or {})
    cwd = Path(cwd).absolute()
    cmdline = [str(x) for x in cmdline]
    print(f"{Fore.BLUE}Running {Style.RESET_ALL} {' '.join(cmdline)}", file=sys.__stderr__)
    print(f"{Fore.BLUE}    inside {Style.RESET_ALL} {cwd}", file=sys.__stderr__)
    ret = subprocess.call(cmdline, cwd=cwd, env=env)
    if ret:
        print(f"Error running {' '.join(cmdline)}", file=sys.__stderr__)
        os.kill(os.getpid(), signal.SIGKILL)
    print(f"{Fore.GREEN}Finished running {Style.RESET_ALL} {' '.join(cmdline)}", file=sys.__stderr__)
    print(f"{Fore.GREEN}    inside {Style.RESET_ALL} {cwd}", file=sys.__stderr__)
