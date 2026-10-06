"""Build a standalone desktop version of Nova Strike for the current platform with PyInstaller.

    python scripts/build_desktop.py   # writes dist/nova-strike-<version>-<platform>.zip (.tar.gz on Linux)

Players don't need Python installed. PyInstaller can't cross-compile, so run this on each platform
you want a build for (the GitHub Actions release workflow does this for Windows, macOS and Linux).
"""

from __future__ import annotations

import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "build" / "desktop"
DIST = ROOT / "dist"
NAME = "Nova Strike"


def version() -> str:
    # read with a regex rather than tomllib, which needs Python 3.11
    match = re.search(r'^version = "(.+)"', (ROOT / "pyproject.toml").read_text(), re.MULTILINE)
    if match is None:
        raise SystemExit("no version found in pyproject.toml")
    return match.group(1)


def platform_tag() -> str:
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    machine = platform.machine().lower()
    arch = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(machine, machine)
    return f"{system}-{arch}"


def main() -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    app_dist = WORK / "dist"
    # a macOS .app must be a folder bundle; elsewhere a single executable is simplest to hand out
    bundle = "--onedir" if sys.platform == "darwin" else "--onefile"
    command = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", bundle,
        "--name", NAME,
        "--distpath", str(app_dist), "--workpath", str(WORK / "work"), "--specpath", str(WORK),
        str(ROOT / "main.py"),
    ]  # fmt: skip
    print("Running:", " ".join(command))
    subprocess.run(command, check=True, cwd=ROOT)

    DIST.mkdir(exist_ok=True)
    archive = DIST / f"nova-strike-{version()}-{platform_tag()}"
    if sys.platform == "darwin":
        # ditto keeps the bundle's symlinks and permissions, which shutil's zip would lose
        target = archive.parent / f"{archive.name}.zip"
        subprocess.run(["ditto", "-c", "-k", "--keepParent", str(app_dist / f"{NAME}.app"), str(target)], check=True)
    elif sys.platform == "win32":
        target = Path(shutil.make_archive(str(archive), "zip", app_dist, f"{NAME}.exe"))
    else:
        # a tarball keeps the executable bit
        target = Path(shutil.make_archive(str(archive), "gztar", app_dist, NAME))
    print(f"Built: {target}")


if __name__ == "__main__":
    main()
