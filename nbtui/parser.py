import logging

from nbtui import _METADATA
from nbtui.cells import *

def parse_nb(json_notebook):
    """
    Parses a json representation of a jupyter notebook,
    and returns a list of cells and their outputs.
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
