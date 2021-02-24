from contextlib import contextmanager
from functools import partial
import os
import re
import signal
import sys
import termios

from rich.prompt import Prompt

from nbtui import _METADATA
from nbtui.parser import TextCell
from nbtui.display import display_notebook

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
    # clamp to end of notebook
    row = min(row, notebook.size - _METADATA["term_height"])

    # negative values indicate end of notebook
    if row < 0:
        row = max(notebook.size - _METADATA["term_height"], 0)

    notebook.row = row
    return False

def search(get_next, notebook):
    # place cursor at bottom of screen
    sys.stdout.buffer.write(b'\033F/')
    search_pat = ".*?" + input("")
    # search_pat = Prompt().ask("/")
    search_pat = re.compile(search_pat)

    notebook.search_pat = search_pat

    return get_next(notebook)

def search_next(notebook):
    for line, cell in notebook.cell_displays.items():
        if line + cell.n_lines < notebook.row:
            continue

        if not isinstance(cell, TextCell):
            continue

        try:
            offset = next(i for i, l in enumerate(cell.text_lines) if
                          (notebook.search_pat.match(l) and
                              i + line > notebook.row))
            # breakpoint()
            goto(line + offset + 2, notebook)
            return False
        except StopIteration:
            continue

def search_prev(notebook):
    for line, cell in reversed(notebook.cell_displays.items()):
        # Skip to the next if we are on the first line of a cell
        if line > notebook.row - 3:
            continue

        if not isinstance(cell, TextCell):
            continue

        try:
            offset = next(i for i, l in enumerate(reversed(cell.text_lines)) if
                          (notebook.search_pat.match(l) and
                              line + i < notebook.row))
            goto(line + offset + 2, notebook)
            return False
        except StopIteration:
            continue

def exit(_):
    return True

input_dict = {
            "j": partial(scroll, 1),
            "k": partial(scroll, -1),
            '\x04': partial(scroll, 15), # CTRL-D
            '\x15': partial(scroll, -15), # CTRL-U
            "G": partial(goto, -1),
            "g": partial(goto, 0),
            "/": partial(search, search_next),
            "n": search_next,
            "N": search_prev,
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
