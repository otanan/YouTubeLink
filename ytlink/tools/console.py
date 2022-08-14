#!/usr/bin/env python3
"""Holds console configuration for printing to terminal by customizing Rich.

**Author: Jonathan Delgado**

"""
#======================== Rich ========================#
#------------- Imports -------------#
import rich.theme, rich.progress, rich.console
# Improved tracebacks
import rich.traceback; rich.traceback.install()
#------------- Settings -------------#
# Store colors as variables for use with library objects
cblue = '#0675BB'
cgreen = 'green'
# Custom theme
theme = rich.theme.Theme({
    # Syntax highlighting for numbers, light mint
    "repr.number": "#9DFBCC",
    #--- Colors ---#
    'blue': cblue,
    'green': cgreen,
    #--- Meaning ---#
    'success': cgreen,
    # Emphasis
    'emph': cblue,
    # Amaranth red
    'warning': '#E03E52',
    'fail': '#E03E52'
})

console = rich.console.Console(theme=theme)
# Override the print and input functionality
print = console.print
input = console.input
# Provide a rich status function for indeterminate progress
rstatus = lambda text: console.status(
    text, spinner='dots', spinner_style=cblue
)
#--- Progress bar ---#
def Progress(label='Progress'):
    """ Overload constructor for generating progress bars. """
    return rich.progress.Progress(
        rich.progress.SpinnerColumn('dots', style=cblue),
        rich.progress.TextColumn(f'{label}:', style=cblue),
        rich.progress.BarColumn(complete_style=cgreen, finished_style=cblue),
        rich.progress.MofNCompleteColumn(),
        console=console
    )
#======================== End Rich ========================#