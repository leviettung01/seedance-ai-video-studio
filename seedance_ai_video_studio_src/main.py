# -*- coding: utf-8 -*-
"""
Seedance AI Video Studio — Entry Point
Khoi dong Tkinter Desktop GUI + FastAPI server nen.
"""

import os
import sys

# Fix Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Module path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import APP_NAME, APP_VERSION


def main():
    print(f"")
    print(f"====================================================")
    print(f"  {APP_NAME} v{APP_VERSION}")
    print(f"  Desktop GUI (Tkinter)")
    print(f"====================================================")
    print(f"")

    from main_gui import main as gui_main
    gui_main()


if __name__ == "__main__":
    main()
