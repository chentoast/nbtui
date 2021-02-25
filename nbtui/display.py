from base64 import standard_b64encode
import sys

import rich
from rich.console import RenderGroup
from rich.markdown import Markdown
from rich.panel import Panel
from rich.padding import Padding
from rich.syntax import Syntax
from rich.text import Text

from nbtui import _METADATA
from nbtui.parser import (TextCell, MDCell, CodeCell, TextOutputCell,
                    DisplayOutputCell, BlankCell, ErrorOutputCell)

_RULE = rich.rule.Rule(style="white", end="")

class Notebook:
    def __init__(self, cells):
        self.cell_displays = {}
        self.cell_renders = {}
        self.plots_todraw = []

        # which line is currently at the top
        self.row = 0
        self.search_pat = None
        self.needs_redraw = False

        display_row = 0

        for cell in cells:
            self.cell_displays[display_row] = cell
            display_row += cell.n_lines


        # This is a bit ugly: if the notebook is too small, rich.Live will
        # not hide the shell prompt, which throws off calculations
        # of display offsets.

        # Therefore, add an artificial empty cell to ensure that
        # the size of the notebook exceeds the terminal height.

        if display_row < _METADATA["term_height"]:
            dummy_text = ["\n" for _ in range(_METADATA["term_height"] - 
                                              display_row + 1)]
            dummy_cell = CodeCell(dummy_text)
            self.cell_displays[display_row] = dummy_cell
            self.cell_renders[display_row] = None

        self.size = max(display_row, _METADATA["term_height"])

    def draw_plot_later(self, cell, start_row):
        self.plots_todraw.append((cell.b64,
            (start_row, int((_METADATA["term_width"] - cell.size[1]) / 2)),
            cell.size))

    def draw_plots(self):
        for (image, pos, size) in self.plots_todraw:
            display_image(image, pos, size)

        self.plots_todraw.clear()

    def get_renders_in_range(self, start, end):
        """
        returns all renders between {start} and {end},
        truncating any starting cells as necessary.
        """
        renders = []
        for k, v in self.cell_displays.items():

            if k + v.n_lines > start and k < start:
                # only part of the cell is showing
                truncated_cell = v.truncate(start - k)

                renderable = render_cell(truncated_cell)

                if truncated_cell.pad:
                    renderable = pad_renderable(renderable, start - k)

                renders.append(renderable)

                if isinstance(truncated_cell, DisplayOutputCell):
                    self.draw_plot_later(truncated_cell,
                            max(3, 5 - (start - k)))

            elif k >= start and k <= end:
                if self.cell_renders.get(k, None) is None:
                    self.cell_renders[k] = pad_renderable(
                            render_cell(self.cell_displays[k]), 0)

                renders.append(self.cell_renders[k])

                if isinstance(v, DisplayOutputCell) and k + v.n_lines <= end:
                    self.draw_plot_later(v, k - start + 5)
                elif isinstance(v, DisplayOutputCell) and k + v.n_lines > end:
                    # Normally, in the case of bottom truncation, we push the
                    # entire renderable on, and let Rich handle the cropping.
                    # However, since plot drawing is done separately,
                    # we have to handle bottom truncation of images ourselves.
                    truncated_cell = v.truncate_bottom(end - k)

                    if isinstance(truncated_cell, DisplayOutputCell):
                        self.draw_plot_later(truncated_cell, 
                                _METADATA["term_height"] - (end - k - 5))

        return renders


def display_notebook(notebook):
    row = notebook.row
    renders = notebook.get_renders_in_range(row, row + _METADATA["term_height"])

    notebook.needs_redraw = False

    return Panel(RenderGroup(*renders))

def render_cell(cell):
    if isinstance(cell, BlankCell):
        return Syntax(" \n" * cell.n_lines, "python",
                      background_color="default")
    elif isinstance(cell, MDCell):
        return Markdown(cell.text)
    elif isinstance(cell, CodeCell):
        return Syntax(cell.text, _METADATA["language"],
                background_color="default")
    elif isinstance(cell, TextOutputCell):
        return Text(cell.text)
    elif isinstance(cell, DisplayOutputCell):
        # draw a large blank space for the plot to fit into
        return Syntax(" \n" * (cell.n_lines - 3), "python",
            background_color="default")
    elif isinstance(cell, ErrorOutputCell):
        return Text.from_markup(cell.tb_text)
    else:
        assert False


def pad_renderable(renderable, offset):
    """
    Pad a renderable, subject to a particular truncation offset.
    """
    if offset < 0:
        raise Exception("invalid offset!")
    if offset == 0:
        return RenderGroup(_RULE, Padding(renderable, 1))
    if offset == 1:
        return Padding(renderable, 1)
    else:
        return Padding(renderable, (0, 1, 1, 1))

def display_image(image, position, size):
    """
    Takes a base 64 encoded image string, and displays it on the screen
    using the kitty graphics protocol.

    image: base 64 encoded png
    """
    # move cursor
    sys.stdout.buffer.write(b'\033[%d;%dH' % position)

    cmd = {"a": "T", "f": 100,  "r": size[0], "c":size[1]}

    while image:
        chunk, image = image[:4096], image[4096:]

        m = 1 if image else 0
        cmd["m"] = m

        cmd_header = ','.join(f'{k}={v}' for k, v in cmd.items())
        cmd_header = cmd_header.encode("ascii")
        payload = b''.join((b'\033_G', cmd_header, b';', chunk, b'\033\\'))

        sys.stdout.buffer.write(payload)
        sys.stdout.flush()

        cmd.clear()
