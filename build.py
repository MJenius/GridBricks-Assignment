"""Vercel build script for Wind Desk.

Compiles the React + TypeScript + Vite frontend so that built SPA assets
in `frontend/dist` are available for CDN promotion and FastAPI single-origin serving.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    root_dir = Path(__file__).resolve().parent
    frontend_dir = root_dir / "frontend"
    print(f"[build.py] Building frontend in: {frontend_dir}")

    # Run npm ci (or npm install as fallback)
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    try:
        print("[build.py] Running npm ci...")
        subprocess.run([npm_cmd, "ci"], cwd=frontend_dir, check=True)
    except Exception as exc:
        print(f"[build.py] 'npm ci' failed ({exc}), falling back to 'npm install'...")
        subprocess.run([npm_cmd, "install"], cwd=frontend_dir, check=True)

    # Compile the production bundle
    print("[build.py] Running npm run build...")
    subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir, check=True)

    dist_index = frontend_dir / "dist" / "index.html"
    if not dist_index.is_file():
        raise RuntimeError(f"[build.py] Expected build artifact {dist_index} does not exist.")

    print(f"[build.py] Build verified. Found {dist_index}")


if __name__ == "__main__":
    main()
