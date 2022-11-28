import sys
import time


def slow_print(s):
    wc = 0
    for c in s:
        print(c, end="")
        sys.stdout.flush()
        wc += 1
        time.sleep(0.003)
        if c == "\n" and wc > 2:
            time.sleep(0.003 * max(1, 80 - wc))
            wc = 0
    print()
