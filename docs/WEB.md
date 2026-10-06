# Playing in a web browser

Nova Strike can run in a web page, using [pygbag](https://pygame-web.github.io/) to package the Python code for
a browser-compatible version of Python and pygame (WebAssembly). The same code runs natively and in the browser.

## Building and playing locally

```bash
venv/bin/pip install -r requirements-web.txt
venv/bin/python scripts/build_web.py --serve
```

Then open <http://localhost:8000>. The first load takes a few seconds; click the page once to start (browsers
require a click before a page may play sound), then press Space.

To build without serving:

```bash
venv/bin/python scripts/build_web.py
```

The finished site is written to `build/web-src/nova-strike/build/web/`.

## Publishing

The build folder is a static website: upload its contents to any static host, such as GitHub Pages, Netlify, or
itch.io (zip the folder and upload it as an HTML game).

The page loads the Python runtime from pygbag's online server, so players need an internet connection.

## Checking a build automatically

`scripts/check_web.py` opens the build in your installed Google Chrome without a visible window, clicks through
the start prompt, starts a game while holding fire, and saves screenshots and the browser console log:

```bash
venv/bin/python scripts/build_web.py
venv/bin/python scripts/check_web.py              # results in build/web-check/
venv/bin/python scripts/check_web.py --debug      # also show pygbag's Python console on the page
```

| Option | Effect |
|---|---|
| `--out DIR` | Where to save the screenshots and `console.log`. |
| `--boot-seconds N` | How long to allow the game to load (default 45). |
| `--size WxH` | Browser window size (default 1280x800). |
| `--debug` | Show Python's output and any errors on the page. Use this if a build shows a blank or grey screen. |

## Differences from the desktop version

| | Desktop | Browser |
|---|---|---|
| High scores | `highscores.json` | The page's local storage (kept across reloads, per browser) |
| Esc | Quits | Pauses (a web page can't close itself) |
| Fullscreen | F / F11, and the window can be resized | Use the browser's own fullscreen |
| Fonts | System monospace font | pygame's built-in font |
| Cmd key | Next weapon | Often taken by browser shortcuts; use Alt and Ctrl |
| Command-line options | Available | Not available: the defaults are used |

## How it works

- `main.py` imports pygame directly. pygbag reads `main.py`'s imports to decide which packages to load, so
  without this the browser gets an incomplete pygame.
- In the browser (`sys.platform == "emscripten"`), `main.py` runs `Game.run_async()`, which hands control back
  to the page after every frame. Natively it runs `Game.run()`. Both call the same `Game.frame()`.
- `scripts/build_web.py` copies only `main.py` and the `nova_strike` package into a clean folder before
  packaging. pygbag packages everything in the folder it is given, so building from the project folder would
  include the virtual environment.
- On the web, the sound code also supports the 32-bit float audio format browsers may use, and key codes the
  browser's pygame doesn't have (such as Cmd) are skipped.

## Troubleshooting

**The build hangs with `CERTIFICATE_VERIFY_FAILED` warnings.** Python installed from python.org on macOS doesn't
use the system's certificates, so pygbag's downloads fail and it retries forever. `build_web.py` avoids this by
pointing Python at the `certifi` certificate bundle. If you run pygbag yourself, set `SSL_CERT_FILE` to the
output of `python -m certifi`, or run "Install Certificates.command" from your Python folder in Applications.

**The page stays grey or shows a Python error.** Run `scripts/check_web.py --debug` and look at the error in the
screenshot, or open the page with `#debug` on the end of its address.
