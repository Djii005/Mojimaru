import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Get the base directory of the project.

    In a compiled/frozen PyInstaller state, this points to the directory containing
    the executable. In source/dev mode, it points to the repository root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent
