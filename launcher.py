"""Top-level launcher script for the PyInstaller-bundled desktop app.

PyInstaller's entry point must be a top-level script (no package context),
which means it can't use the relative imports (`from . import naming`) that
zoho_video_renamer/gui.py uses internally. This thin wrapper:

  1. Imports the GUI module by its absolute package path
  2. Calls its main() function

so the bundled binary works while the package source keeps proper relative
imports for normal Python usage.
"""

if __name__ == "__main__":
    from zoho_video_renamer.gui import main
    main()
