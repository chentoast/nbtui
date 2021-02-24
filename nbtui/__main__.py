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

from nbtui import _METADATA, _CAN_PARSE
from display import display_notebook, Notebook
from parser import parse_nb, reparse_nb
from user_input import get_char, handle_input

def parse_metadata():
    term_width, term_height= os.get_terminal_size()
    if (term_width == _METADATA.get("term_width", None) and 
        term_height == _METADATA.get("term_height", None)):
        return

    buf = array.array('H', [0, 0, 0, 0])
    fcntl.ioctl(sys.stdout, termios.TIOCGWINSZ, buf)
    screen_width = buf[2]
    screen_height = buf[3]

    if screen_height != 0 and screen_width != 0:
        _CAN_PARSE.add("display_data")


    pixels_per_row = screen_height / term_height
    pixels_per_col = screen_width / term_width

    _METADATA["term_height"] = term_height
    _METADATA["term_width"] = term_width
    _METADATA["screen_width"] = buf[2]
    _METADATA["screen_height"] = buf[3]
    _METADATA["pix_per_row"] = pixels_per_row
    _METADATA["pix_per_col"] = pixels_per_col

def worker(queue, filename):

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

def main(filename):
    if filename[-6:] != ".ipynb":
        raise Exception("Only accepts jupyter notebooks")
    
    with open(filename, "r") as f:
        nb = json.load(f)

    parse_metadata()
    notebook = Notebook(parse_nb(nb))

    queue = mp.Queue()
    p = mp.Process(target=worker, daemon=True, args=(queue, filename))
    p.start()

    rendered_cells = display_notebook(notebook)

    stop = False
    with Live(transient=True,
              auto_refresh=False,
              vertical_overflow="crop",
              redirect_stdout=False) as live:


        live.update(rendered_cells, refresh=True)
        notebook.draw_plots()
        while not stop:
            if not queue.empty():
                new_nb = queue.get()
                reparse_nb(new_nb, notebook)

            if notebook.needs_redraw:
                rendered_cells = display_notebook(notebook)

                sys.stdout.buffer.write(b"\x1b[2J\x1b[H")
                live.update(rendered_cells, refresh=True)
                notebook.draw_plots()

            char = get_char()

            # TODO: We really only need to reparse metadata on resize,
            # instead of in every loop.
            parse_metadata()
            stop = handle_input(char, notebook)

    queue.close()
    p.join()
    sys.stdout.buffer.write(b"\x1b[2J\x1b[H")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", type=str)
    args = parser.parse_args()

    main(args.filename)
