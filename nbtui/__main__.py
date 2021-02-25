#!/bin/python

import argparse
import array
import fcntl
import json
import multiprocessing as mp
import sys
import termios
import os

import rich
from rich.live import Live
from watchgod import run_process, RegExpWatcher

from nbtui import _METADATA
from nbtui.display import display_notebook, Notebook
from nbtui.parser import parse_nb, reparse_nb
from nbtui.user_input import SetTermAttrs, get_char, handle_input

def check_resized():
    term_width, term_height= os.get_terminal_size()
    return (term_width != _METADATA.get("term_width", None) or
            term_height != _METADATA.get("term_height", None))

def parse_metadata():
    term_width, term_height= os.get_terminal_size()

    buf = array.array('H', [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    screen_width = buf[2]
    screen_height = buf[3]

    _METADATA["img_support"] = False
    if screen_height != 0 and screen_width != 0:
        _METADATA["img_support"] = True

    pixels_per_row = screen_height / term_height
    pixels_per_col = screen_width / term_width

    _METADATA["term_height"] = term_height
    _METADATA["term_width"] = term_width
    _METADATA["screen_width"] = buf[2]
    _METADATA["screen_height"] = buf[3]
    _METADATA["pix_per_row"] = pixels_per_row
    _METADATA["pix_per_col"] = pixels_per_col

def filewatch_worker(queue, filename):

    def on_changed(queue, filename):
        with open(filename, "r") as f:
            new_nb = json.load(f)
        queue.put(new_nb)

    sys.stderr = open(os.devnull, "w")
    sys.stdout = open(os.devnull, "w")

    filename = os.path.realpath(filename)
    start_dir = os.path.dirname(filename)
    run_process(start_dir, on_changed, watcher_cls = RegExpWatcher,
            watcher_kwargs = {"re_files": filename},
            args=(queue, filename))

def input_worker(in_queue, out_queue):
    sys.stdin = open(0)
    fd = sys.stdin.fileno()
    while True:
        with SetTermAttrs(fd):
            c = get_char()
            in_queue.put(c)

        # Block until main proc has processed the keypress
        # this is so we don't clobber stdin for things like searching,
        # where the user types additional characters after the inital
        # press of /
        _ = out_queue.get()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", type=str)
    args = parser.parse_args()

    filename = args.filename

    if filename[-6:] != ".ipynb":
        raise Exception("Only accepts jupyter notebooks")
    
    with open(filename, "r") as f:
        nb = json.load(f)

    _METADATA["language"] = nb["metadata"]["kernelspec"]["language"]
    parse_metadata()
    notebook = Notebook(parse_nb(nb))

    filewatch_queue = mp.Queue()
    filewatch_p = mp.Process(target=filewatch_worker,
                             args=(filewatch_queue, filename))
    filewatch_p.start()

    input_queue = mp.Queue()
    out_queue = mp.Queue()
    input_p = mp.Process(target=input_worker, daemon=True,
                         args=(input_queue, out_queue))
    input_p.start()

    rendered_cells = display_notebook(notebook)

    with Live(transient=True,
              auto_refresh=False,
              vertical_overflow="crop",
              redirect_stdout=False) as live:

        live.update(rendered_cells, refresh=True)
        notebook.draw_plots()
        char = ''
        stop = False
        while not stop:
            if notebook.needs_redraw:
                rendered_cells = display_notebook(notebook)

                sys.stdout.buffer.write(b"\x1b[2J\x1b[H")
                live.update(rendered_cells, refresh=True)
                notebook.draw_plots()

            if not filewatch_queue.empty():
                new_nb = filewatch_queue.get()
                notebook = reparse_nb(new_nb, notebook)

            if not input_queue.empty():
                char = input_queue.get()
                stop = handle_input(char, notebook)
                # signal that the keypress was handled
                out_queue.put(1)

            if check_resized():
                parse_metadata()
                notebook.needs_redraw = True

    filewatch_queue.close()
    input_queue.close()

    # input subproc will be automatically closed, since it was initialized
    # as a daemon
    filewatch_p.terminate()
    filewatch_p.join()
    sys.stdout.buffer.write(b"\x1b[2J\x1b[H")

if __name__ == "__main__":
    main()
