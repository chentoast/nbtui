# NBTui

An interactive viewer for Jupyter notebooks from the command line.
Currently only supports python, but support for other languages is
planned for the future.

It should work for any terminal, but you will only be able to view
images when using Kitty, or any terminal that implements the Kitty
graphics protocol.

## Install

```python
pip install nbtui
```

## Features

- Vim-style keybindings for scrolling and movement
- Regex searching
- View images and plots
- Automatic file-change detection

## Usage

Movement and scrolling is based on vim keybindings - j to scroll down,
k to scroll up, C-D to scroll down by 15 lines, C-U to scroll up
by 15 lines.
Press g and G to go to the beginning and end of the notebook,
respectively.

NOTE: currently, displaying images is done in a quite inefficient way.
I plan to update this logic soon to take advantage
of new features from the Kitty graphics protocol, once Kitty version 0.19.3
has been out for a little while longer.

In the meantime, prefer using C-D and C-U to scrolling when images
are on the screen, to avoid large slowdowns.

## Planned features

- Support other display data formats besides just png
- Other languages
- Better configurability, through command line arguments or env variables
- Fix slow scrolling with images by utilizing Kitty placement ids
