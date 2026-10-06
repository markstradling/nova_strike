"""Launch Nova Strike. Run ``python main.py --help`` for options.

The same file starts the browser build: pygbag runs it under WebAssembly (sys.platform
"emscripten"), where the game needs an async main loop that yields to the page each frame.
"""

import asyncio
import sys

import pygame  # noqa: F401 - pygbag scans this file's imports to decide which packages the page loads

from nova_strike.cli import main, main_async

if __name__ == "__main__":
    if sys.platform == "emscripten":
        asyncio.run(main_async())
    else:
        main()
