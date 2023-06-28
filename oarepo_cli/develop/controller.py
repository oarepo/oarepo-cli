import errno
import os
import queue
import select
import sys

# Controller is a class that gets commands from user - it may be a terminal controller, where the input
# is taken from stdin, or pipe controller, where the input is taken from a unix pipe
# The input is then put to a blocking queue
# The controller is run as a daemon thread from the main loop.


class TerminalController:
    def run(self, queue: queue.Queue):
        print("Terminal controller running")
        running = True
        while running:
            cmd = self.input_with_timeout(60)
            if not cmd:
                continue
            print("Accepted command from terminal", cmd)
            if cmd == "stop":
                running = False
            queue.put(cmd)

    def input_with_timeout(self, timeout):
        print("=======================================================================")
        print()
        print("Type: ")
        print()
        print("    server <enter>    --- restart server")
        print("    ui <enter>        --- restart ui watcher")
        print("    build <enter>     --- stop server and watcher, ")
        print("                          call ui build, then start again")
        print("    stop <enter>      --- stop the server and ui and exit")
        print()
        i, o, e = select.select([sys.stdin], [], [], timeout)

        if i:
            return sys.stdin.readline().strip()


class PipeController:
    def __init__(self, pipe_path):
        self.pipe_path = pipe_path
        print(f"making fifo at {pipe_path=}")
        try:
            os.mkfifo(pipe_path)
        except OSError as oe:
            print(f"{pipe_path=} {oe=}")
            if oe.errno != errno.EEXIST:
                raise

    def run(self, queue: queue.Queue):
        print("Pipe controller running")
        running = True
        while running:
            print("Waiting on queue")
            with open(self.pipe_path) as fd:
                for cmd in fd.readline():
                    cmd = cmd.strip()
                    print("Accepted command from queue", cmd)
                    if cmd == "stop":
                        running = False

                    queue.put(cmd)
                    if not running:
                        break
