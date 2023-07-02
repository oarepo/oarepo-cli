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
        running = True
        try:
            while running:
                cmd = self.input_with_timeout(60)
                if not cmd:
                    continue
                if cmd == "stop":
                    running = False
                queue.put(cmd)
        except InterruptedError:
            queue.put("stop")

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
        try:
            os.mkfifo(pipe_path)
        except OSError as oe:
            if oe.errno != errno.EEXIST:
                raise

    def run(self, queue: queue.Queue):
        running = True
        while running:
            with open(self.pipe_path) as fd:
                cmd = fd.read(1024)
                if not cmd:
                    continue
                cmd = cmd.strip()
                if cmd == "stop":
                    running = False
                queue.put(cmd)
                if not running:
                    break
