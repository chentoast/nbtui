from contextlib import contextmanager
from functools import partial
import os
import signal
import sys
import termios

from display import display_notebook
from nbtui import _METADATA

# Taken from https://www.jujens.eu/posts/en/2018/Jun/02/python-timeout-function/
@contextmanager
def timeout(secs):
    def raise_error(signum, frame):
        raise TimeoutError

    signal.signal(signal.SIGALRM, raise_error)
    signal.alarm(secs)

    try:
        yield
    except TimeoutError:
        pass
    finally:
        # Unregister the signal so it won't be triggered
        # if the timeout is not reached.
        signal.signal(signal.SIGALRM, signal.SIG_IGN)

def get_char():
    fd = sys.stdin.fileno()

    oldterm = termios.tcgetattr(fd)
    newattr = termios.tcgetattr(fd)
    # Disable CANONICAL and ECHO modes for stdin lflags, so 
    # that input becomes available immediately, instaed of after
    # newline
    newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, newattr)

    c = None
    with timeout(1):
        c = sys.stdin.read(1)

    termios.tcsetattr(fd, termios.TCSAFLUSH, oldterm)

    return c if c else ""

def scroll(n, notebook):
    if notebook.row + n <= 0:
        notebook.row = 0
    elif notebook.row + n >=notebook.size - _METADATA["term_height"]:
        notebook.row = notebook.size - _METADATA["term_height"]
    else:
        notebook.row += n
    return False

def goto(row, notebook):
    # negative values indicate end of notebook
    if row < 0:
        row = max(notebook.size - _METADATA["term_height"], 0)

    notebook.row = row

def exit(_):
    return True

input_dict = {
            "j": partial(scroll, 1),
            "k": partial(scroll, -1),
            '\x04': partial(scroll, 15), # CTRL-D
            '\x15': partial(scroll, -15), # CTRL-U
            "G": partial(goto, -1),
            "g": partial(goto, 0),
            'q': exit,
        }

def handle_input(char, notebook):
    if char == "":
        return False
    try:
        stop = input_dict[char](notebook)
        notebook.needs_redraw = True
        return stop
    except KeyError:
        return False
