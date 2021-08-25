from base64 import decodebytes, b64encode
import io
from math import ceil, floor
import re

from PIL import Image
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.text import Text

from nbtui import _METADATA

class BlankCell:
    pad = False

    def __init__(self, n):
        self.n_lines = n

    def render(self, notebook):
        return Syntax(" \n" * self.n_lines, "python",
                      background_color="default")

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

    def render(self, notebook):
        pass

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

if __name__ == "__main__":
    out = ErrorOutputCell.fix_markup("[red]hello [/][blue] world [/][/]")

class MDCell(TextCell):
    def render(self, notebook):
        return Markdown(self.text)

class CodeCell(TextCell):
    def render(self, notebook):
        return Syntax(self.text, _METADATA["language"],
                background_color="default")

class TextOutputCell(TextCell):
    def render(self, notebook):
        return Text(self.text)

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

    def render(self, notebook):
        return Text.from_markup(self.tb_text)

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

    def render(self, notebook):
        # first draw a blank canvas for the image to sit on top of, and then
        # register the image to be drawn later.
        # notebook.draw_plot_later(self, max(3, 5 - (start - k)))
        return Syntax(" \n" * (self.n_lines - 3), "python",
            background_color="default")

    @staticmethod
    def img_to_b64(img):
        stream = io.BytesIO()
        img.save(stream, format="png")
        return b64encode(stream.getvalue())


