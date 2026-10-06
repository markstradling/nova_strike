"""Build (or serve) the browser version of Nova Strike with pygbag.

    python scripts/build_web.py           # build into build/web-src/nova-strike/build/web/
    python scripts/build_web.py --serve   # build and serve at http://localhost:8000

pygbag packages every file in the folder it's given, so the game code is first copied into a
clean folder: that keeps the virtualenv, tests and caches out of the download.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

import certifi

ROOT = Path(__file__).resolve().parent.parent
STAGING = ROOT / "build" / "web-src" / "nova-strike"
OUTPUT = STAGING / "build" / "web"


def stage() -> None:
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.mkdir(parents=True)
    shutil.copy2(ROOT / "main.py", STAGING / "main.py")
    shutil.copytree(ROOT / "nova_strike", STAGING / "nova_strike", ignore=shutil.ignore_patterns("__pycache__"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--serve", action="store_true", help="serve the build at http://localhost:8000")
    args = parser.parse_args()

    stage()
    command = [sys.executable, "-m", "pygbag", "--title", "Nova Strike"]
    if not args.serve:
        command.append("--build")
    command.append(str(STAGING))
    # pygbag downloads its page template and runtime over HTTPS. Python.org's macOS builds don't
    # use the system certificates, so without this those downloads fail and pygbag retries forever.
    env = {**os.environ, "SSL_CERT_FILE": os.environ.get("SSL_CERT_FILE", certifi.where())}
    print("Running:", " ".join(command))
    subprocess.run(command, check=True, env=env)
    if not args.serve:
        print(f"Built: {OUTPUT}")
        print("Upload that folder to any static web host, or run with --serve to try it locally.")


if __name__ == "__main__":
    main()
