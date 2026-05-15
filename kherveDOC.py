"""Launcher — run this file to start kherveDOC.

Equivalent to `python -m khervedoc` but lets you double-click the file or
hand it to an IDE's run button.
"""
import sys
from pathlib import Path

# Make the package importable when this file is run directly.
sys.path.insert(0, str(Path(__file__).parent))

from khervedoc.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
