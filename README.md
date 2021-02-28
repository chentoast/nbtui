# NBTui

![demo](../assets/demo.gif?raw=true)

An interactive viewer for Jupyter notebooks from the command line.

It should work for any terminal, but you will only be able to view
plots when using Kitty, or any terminal that implements the Kitty
graphics protocol.

This is a work in progress, and things may break. Bug reports and general
constructive criticism about implementation details are welcome.

## Install

```python
pip install nbtui

nbtui {NOTEBOOK}.ipynb
```

Or, you can directly pull this folder from master (this is recommended, since there are most likely still going to be some issues):

```
python -m nbtui {NOTEBOOK}.ipynb
```

## Features

- Vim-style keybindings for scrolling and movement
- Regex searching
- View images and plots
- Automatic file-change detection and refresh (somewhat experimental)

## Usage

Movement and scrolling is based on vim keybindings - j to scroll down,
k to scroll up, C-D to scroll down by 15 lines, C-U to scroll up
by 15 lines.
Press g and G to go to the beginning and end of the notebook,
respectively, press / to start searching, and press q to close.

NOTE: currently, displaying images is done in a quite inefficient way.
I plan to update this logic soon to take advantage
of new features from the Kitty graphics protocol, once Kitty version 0.19.3
has been out for a little while longer.

In the meantime, prefer using C-D and C-U to scrolling when many images
are on the screen, to avoid large slowdowns.

## Planned features

For obvious reasons, rich output formats like HTML, PDF, Javascript, videos,
audio, and hyperlinks are not planned to be implemented.

- Support other display data formats
    - Plot backends besides just png
    - Latex in markdown cells
    - Linking of images (JPEG, SVG)
    - Progress bars
- Better handling of multiple outputs for a single cell. We should show
these things in a single large output cell instead of breaking it up.
- Better configurability. Users should be able to configure things like themes
for syntax highlighting, padding, etc.
- Fix slow scrolling with images by utilizing Kitty placement ids
- Folding
