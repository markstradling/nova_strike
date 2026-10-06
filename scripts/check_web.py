"""Smoke-test the browser build in headless Chrome: does the game boot and respond to keys?

    python scripts/build_web.py && python scripts/check_web.py [--out DIR]

Serves the built page locally, opens it in your installed Chrome via Playwright, clicks through
pygbag's start prompt, starts a game, and saves screenshots plus the browser console log.
The page fetches pygbag's WebAssembly runtime from its CDN, so this needs an internet connection.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build" / "web-src" / "nova-strike" / "build" / "web"
PORT = 8765


def serve() -> http.server.ThreadingHTTPServer:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(BUILD))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "web-check", help="where to save screenshots")
    parser.add_argument("--boot-seconds", type=float, default=45, help="how long to allow the game to load")
    parser.add_argument("--debug", action="store_true", help="show pygbag's Python console alongside the game")
    parser.add_argument("--size", default="1280x800", help="browser window size, e.g. 1280x800")
    args = parser.parse_args()
    if not (BUILD / "index.html").exists():
        raise SystemExit("No build found: run scripts/build_web.py first")
    args.out.mkdir(parents=True, exist_ok=True)

    server = serve()
    console: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome", headless=True, args=["--autoplay-policy=no-user-gesture-required"]
        )
        width, height = (int(v) for v in args.size.split("x"))
        page = browser.new_page(viewport={"width": width, "height": height})
        page.on("console", lambda msg: console.append(f"[{msg.type}] {msg.text}"))
        page.on("pageerror", lambda err: console.append(f"[pageerror] {err}"))
        page.goto(f"http://127.0.0.1:{PORT}/index.html" + ("#debug" if args.debug else ""))
        # pygbag shows a "click to start" prompt once loaded (browsers need a click before playing audio),
        # so keep clicking until the game is up.
        for _ in range(int(args.boot_seconds // 3)):
            page.wait_for_timeout(3000)
            page.mouse.click(width // 2, height // 2)
        page.screenshot(path=str(args.out / "1-title.png"))
        page.mouse.click(width // 2, height // 2)  # make sure the canvas has keyboard focus
        page.keyboard.press("Space")
        page.keyboard.down("Space")  # hold fire for a while
        page.wait_for_timeout(4000)
        page.keyboard.up("Space")
        page.screenshot(path=str(args.out / "2-playing.png"))
        browser.close()
    server.shutdown()
    (args.out / "console.log").write_text("\n".join(console))
    print(f"Screenshots and console log saved to {args.out}")
    errors = [line for line in console if "Traceback" in line or "Error" in line or "pageerror" in line]
    print("\n".join(errors[-20:]) if errors else "No errors in the console.")


if __name__ == "__main__":
    main()
