import time

import click
import psutil

@click.command(name="kill")
@click.argument('pid', type=int)
def kill(pid):
    process = psutil.Process(pid)
    to_kill = [process] + list(process.children(True))
    to_kill.reverse()
    print(f"Going to kill {[x.pid for x in to_kill]}")

    # first round - send terminate
    for c in to_kill:
        if c.is_running():
            print(f"Terminating {c.pid} {c.cmdline()}")
            c.terminate()

    # if all killed, return
    for c in to_kill:
        if c.is_running():
            break
    else:
        return   # all terminated

    # wait a bit and try again
    time.sleep(2)

    # if all killed after waiting, return
    for c in to_kill:
        if c.is_running():
            break
    else:
        return   # all terminated

    # send the rest sigkill
    for c in to_kill:
        if c.is_running():
            print(f"Killing {c.pid} {c.cmdline()}")
            c.kill()
