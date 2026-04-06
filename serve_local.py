from __future__ import annotations

import argparse
import os
import subprocess
import sys
import threading
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).parent
DEFAULT_WATCH_PATTERNS = (
    "*.py",
    "*.html",
    "*.css",
    "*.js",
    "*.csv",
    "data/*.json",
    "20[0-9][0-9]/*/ent_all_results.json",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the journal club site locally with an optional rebuild watcher."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host/interface to bind. Default: 127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to serve on. Default: 8000",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Start the server without running populate_sessions.py and build_journal_club.py first.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch project files and rebuild derived data when inputs change.",
    )
    parser.add_argument(
        "--watch-interval",
        type=float,
        default=1.0,
        help="Seconds between watch scans. Default: 1.0",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Open the local site in the default browser after the server starts.",
    )
    return parser.parse_args()


def run_build() -> None:
    commands = [
        [sys.executable, "populate_sessions.py"],
        [sys.executable, "build_journal_club.py"],
    ]
    for cmd in commands:
        subprocess.run(cmd, cwd=ROOT, check=True)


def iter_watch_files() -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in DEFAULT_WATCH_PATTERNS:
        for path in ROOT.glob(pattern):
            if path.is_file() and path not in seen:
                files.append(path)
                seen.add(path)
    return files


def snapshot_mtimes() -> dict[Path, int]:
    mtimes: dict[Path, int] = {}
    for path in iter_watch_files():
        try:
            mtimes[path] = path.stat().st_mtime_ns
        except FileNotFoundError:
            continue
    return mtimes


def watch_for_changes(interval: float) -> None:
    previous = snapshot_mtimes()
    while True:
        time.sleep(interval)
        current = snapshot_mtimes()
        if current == previous:
            continue

        changed = sorted(
            str(path.relative_to(ROOT))
            for path in set(previous) | set(current)
            if previous.get(path) != current.get(path)
        )
        print("\nDetected changes:")
        for rel in changed[:12]:
            print(f"  - {rel}")
        if len(changed) > 12:
            print(f"  - ... and {len(changed) - 12} more")

        try:
            run_build()
            print("Rebuilt derived site data.")
        except subprocess.CalledProcessError as exc:
            print(f"Rebuild failed with exit code {exc.returncode}.")

        previous = current


def main() -> int:
    args = parse_args()

    if not args.skip_build:
        run_build()

    handler = partial(SimpleHTTPRequestHandler, directory=str(ROOT))
    httpd = ThreadingHTTPServer((args.host, args.port), handler)
    url = f"http://{args.host}:{args.port}/"

    print(f"Serving {ROOT} at {url}")
    if args.watch:
        watcher = threading.Thread(
            target=watch_for_changes,
            kwargs={"interval": args.watch_interval},
            daemon=True,
        )
        watcher.start()
        print(f"Watching source files every {args.watch_interval:.1f}s for rebuilds.")

    if args.open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping local server.")
    finally:
        httpd.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
