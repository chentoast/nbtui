from base64 import decodebytes, b64encode
from dataclasses import dataclass
import io
from math import ceil, floor
import logging
import re

from PIL import Image

from nbtui import _METADATA
import nbtui.display

def parse_nb(json_notebook):
    """
    Parses a json representation of a jupyter notebook,
    and returns a list of cells and their outputs, thus representing
    the parsed notebook.
    """
    json_notebook = json_notebook["cells"]
    parsed_cells = []
    for cell in json_notebook:
        parsed_cells.append(parse_nb_cell(cell))
        # break up cells and outputs into distinct units
        if cell.get("outputs", None) is not None:
            for output in cell["outputs"]:
                output_cell = parse_nb_output(output)
                if output_cell is not None:
                    parsed_cells.append(output_cell)

    return parsed_cells

def parse_nb_cell(cell):
    if cell["cell_type"] == "markdown":
        return MDCell(cell["source"])
    
    return CodeCell(cell["source"])

def parse_nb_output(output):
    if output["output_type"] == "stream":
        return CodeCell(output["text"])
    elif output["output_type"] == "error":
        return ErrorOutputCell(output["traceback"])
    elif output["output_type"] == "display_data":
        im = try_parse_image(output)
        if im is not None:
            return DisplayOutputCell(im, "png")

        # if there is no png, just return a blank line
        return BlankCell(1)
    elif output["output_type"] == "execute_result":
        im = try_parse_image(output)
        if im is not None:
            return DisplayOutputCell(im, "png")

        json = output["data"].get("application/json", None)
        if json is not None:
            return CodeCell([str(json)])

        # if we didn't find anything else, return the text
        text = output["data"].get("text/plain", None)
        if text is not None:
            return TextOutputCell(text)
    raise Exception(
            f"Encountered unparsable cell output type {output['output_type']}"
            )

def reparse_nb(json_notebook, parsed_notebook):
    """
    Given a modified version of the notebook,
    reparse the notebook and update any changes.
    For now, re-render everything on change
    """
    num_cells = 0

    for cell in json_notebook["cells"]:
        num_cells += 1
        try:
            num_cells += len(cell["outputs"])
        except:
            pass

    if num_cells != len(parsed_notebook.cell_displays):
        # TODO: Can we avoid reparsing the entire notebook
        # whenever a cell is added/deleted?
        new_nb = nbtui.display.Notebook(parse_nb(json_notebook))
        new_nb.needs_redraw = True
        return new_nb

    json_notebook = json_notebook["cells"]

    parsed_cells = list(parsed_notebook.cell_displays.items())

    offset = 0
    new_cells = {}

    for cell in json_notebook:
        display_line, old_cell = parsed_cells.pop(0)
        if old_cell.compare(cell):
            new_cells[display_line + offset] = old_cell
        else:
            new_cell = parse_nb_cell(cell)
            offset += new_cell.n_lines - old_cell.n_lines
            new_display_line = offset + display_line
            # The display row of the first cell doesn't change
            if display_line == 0:
                new_display_line = 0
            new_cells[new_display_line] = new_cell

        if cell.get("outputs", None) is not None:
            for output in cell["outputs"]:

                display_line, old_output = parsed_cells.pop(0)
                # breakpoint()
                if old_output.compare(output):
                    new_cells[display_line + offset] = old_output
                else:
                    new_output = parse_nb_output(output)
                    offset += new_output.n_lines - old_output.n_lines
                    new_cells[display_line + offset] = new_output

    parsed_notebook.cell_displays = new_cells
    parsed_notebook.cell_renders = {}
    parsed_notebook.needs_redraw = True

    return parsed_notebook

def try_parse_image(cell):
    if not _METADATA["img_support"]:
        return None

    return cell["data"].get("image/png", None)

class BlankCell:
    pad = False

    def __init__(self, n):
        self.n_lines = n

    def register_draw(self, notebook, offset):
        pass

    def compare(self, cell):
        return True

class TextCell:
    pad = True

    def __init__(self, text):
        self.for_compare = hash("".join(text))

        self.n_lines = len(text) + 3
        # to ensure blank lines get rendered correctly,
        # replace a blank line with a single space
        self.text_lines = text
        self.text = "".join((t if t != "\n" else " \n" for t in text))

    def truncate(self, offset):
        if offset >= self.n_lines - 1:
            return BlankCell(1)
        idx = max(offset - 2, 0)
        truncated_lines = self.text_lines[idx:]
        return type(self)(truncated_lines)

    def compare(self, cell):
        return self.for_compare == hash(TextCell.get_text_from_json(cell))

    @staticmethod
    def get_text_from_json(json_cell):
        if json_cell.get("cell_type", None) in ("code", "markdown"):
            return "".join(json_cell["source"])

        # must be an output cell
        if json_cell["output_type"] == "stream":
            return "".join(json_cell["text"])

        # must be execute_result
        json = json_cell["data"].get("application/json", None)
        if json is not None:
            return str(json)

        return "".join(json_cell["data"]["text/plain"])

class MDCell(TextCell):
    pass

class CodeCell(TextCell):
    pass

class TextOutputCell(TextCell):
    pass

@dataclass
class ErrorOutputCell:
    ANSI_COLOR_DICT = {
            "\x1b[0;31m": "[red]",
            "\x1b[0;32m": "[green]",
            "\x1b[0;33m": "[yellow]",
            "\x1b[0;34m": "[blue]",
            "\x1b[0;35m": "[magenta]",
            "\x1b[0;36m": "[cyan]",
            "\x1b[0;37m": "[white]",
            "\x1b[1;31m": "[bold red]",
            "\x1b[1;32m": "[bold green]",
            "\x1b[1;33m": "[bold yellow]",
            "\x1b[1;34m": "[bold blue]",
            "\x1b[1;35m": "[bold magenta]",
            "\x1b[1;36m": "[bold cyan]",
            "\x1b[1;37m": "[bold white]",
            "\x1b[0m":    "[/]"
            }
    pad = True

    def __init__(self, traceback, needs_processing=True):
        self.for_compare = hash("".join(traceback))

        self.traceback = []
        if needs_processing:
            # Jupyter notebook traceback comes with a bunch of ansi
            # color escape codes. We need to convert these to rich
            # markup, in order for these to be displayed correctly.
            for entry in traceback:
                entry = entry.replace("-", "─")
                entry = entry.replace("─>", "─→")
                for color, markup in self.ANSI_COLOR_DICT.items():
                    entry = entry.replace(color, markup)

                rows = entry.split("\n")
                for row in rows:
                    row = self.fix_markup(row)
                    self.traceback.append(row if row != "\n" else " \n")
        else:
            self.traceback = traceback

        self.tb_text = "\n".join(self.traceback)
        self.n_lines = len(self.traceback) + 3

    def truncate(self, offset):
        idx = max(offset - 2, 0)
        return ErrorOutputCell(self.traceback[idx:], needs_processing=False)

    def compare(self, other):
        other_text = "".join(other["traceback"])
        return self.for_compare == hash(other_text)

    @staticmethod
    def fix_markup(text):
        n_style = 0
        idx = 0
        while True:
            pos = re.search("\[(.*?)\]", text[idx:])
            if not pos:
                break

            if pos.group(1) == "/":
                n_style -= 1
            else:
                n_style += 1

            if n_style < 0:
                text = text[:idx + pos.span()[0]] + text[idx + pos.span()[1]:]
                n_style = 0
            else:
                idx += pos.span()[1]

        return text

class DisplayOutputCell:
    def __init__(self, b64_data, fmt):
        self.for_compare = hash(b64_data)

        # strip off the final newline
        b64 = b64_data.encode("ascii")[:-1]
        self.b64 = b64
        self.fmt = fmt

        # note - PIL sizes are (width x height)
        self.img = Image.open(io.BytesIO(decodebytes(b64)))
        width = self.img.size[0]
        height = self.img.size[1]

        if (width >= (_METADATA["term_width"] / 1.5) *
                _METADATA["pix_per_col"] or 
            height >= (_METADATA["term_height"] / 1.5) *
                _METADATA["pix_per_row"]):

            width = min(width, floor((_METADATA["term_width"] / 1.5) *
                                     _METADATA["pix_per_col"]))
            height = min(height, floor((_METADATA["term_height"] / 1.5) *
                                       _METADATA["pix_per_row"]))
            self.img = self.img.resize((width, height))
            self.b64 = self.img_to_b64(self.img)

        self.size = (ceil(height / _METADATA["pix_per_row"]),
                     ceil(width / _METADATA["pix_per_col"]))
        self.n_lines = self.size[0] + 5
        self.pad = True

    def truncate(self, offset):
        if offset <= 2:
            return self
        if offset >= self.n_lines - 4:
            return BlankCell(self.n_lines - offset)

        offset_in_px = ceil((offset - 2) * _METADATA["pix_per_row"])
        new_img = self.img.crop((0, offset_in_px,
            self.img.size[0], self.img.size[1]))

        new_data = DisplayOutputCell.img_to_b64(new_img).decode("utf-8") + "\n"
        return DisplayOutputCell(new_data, self.fmt)

    def truncate_bottom(self, offset):
        if offset <= 4:
            return BlankCell(1)
        
        offset_in_px = ceil((offset - 4) * _METADATA["pix_per_row"])

        new_img = self.img.crop((0, 0, self.img.size[0],
            offset_in_px))

        new_data = DisplayOutputCell.img_to_b64(new_img).decode("utf-8") + "\n"
        return DisplayOutputCell(new_data, self.fmt)

    def compare(self, other):
        return self.for_compare == hash(other["data"]["image/png"])

    @staticmethod
    def img_to_b64(img):
        stream = io.BytesIO()
        img.save(stream, format="png")
        return b64encode(stream.getvalue())

if __name__ == "__main__":
    out = ErrorOutputCell.fix_markup("[red]hello [/][blue] world [/][/]")
