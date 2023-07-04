import time

import click
import psutil


@click.command(name="kill", hidden=True)
@click.argument("pid", type=int)
def kill_command(pid):
    kill(pid)


def kill(pid):
    try:
        process = psutil.Process(pid)
    except Exception as e:
        print(e)
        return

    to_kill = [process] + list(process.children(True))
    to_kill.reverse()
    print(f"Going to kill {[x.pid for x in to_kill]}")

    # first round - send terminate
    for c in to_kill:
        if c.is_running():
            try:
                print(f"Terminating {c.pid} {' '.join(c.cmdline())}")
            except:
                pass
            c.terminate()

    # if all killed, return
    for c in to_kill:
        if c.is_running():
            break
    else:
        return  # all terminated

    # wait a bit and try again
    time.sleep(2)

    # if all killed after waiting, return
    for c in to_kill:
        if c.is_running():
            break
    else:
        return  # all terminated

    # send the rest sigkill
    for c in to_kill:
        if c.is_running():
            try:
                print(f"Killing {c.pid} {c.cmdline()}")
            except:
                pass
            c.kill()
