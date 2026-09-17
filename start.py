#!/usr/bin/env python3
"""Build the React frontend and start the Django backend with one command."""

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"


def main():
    skip_build = "--skip-build" in sys.argv
    server_args = [arg for arg in sys.argv[1:] if arg != "--skip-build"]

    if not skip_build:
        npm = shutil.which("npm")
        if not npm:
            raise SystemExit("npm was not found. Install Node.js or run: python start.py --skip-build")
        if not (FRONTEND / "node_modules").exists():
            print("Installing React dependencies…")
            subprocess.run([npm, "install"], cwd=FRONTEND, check=True)
        print("Building React frontend…")
        subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)

    print("Starting Business Data Finder at http://127.0.0.1:8000/ …")
    command = [sys.executable, str(ROOT / "manage.py"), "runserver", *server_args]
    raise SystemExit(subprocess.call(command, cwd=ROOT))


if __name__ == "__main__":
    main()
