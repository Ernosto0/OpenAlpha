from __future__ import annotations

import argparse
import os
import signal
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openalpha",
        description="OpenAlpha local development commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Start the local OpenAlpha backend and frontend.",
    )
    run_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project root to run. Defaults to the current directory.",
    )
    run_parser.set_defaults(func=run_app)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


def run_app(args: argparse.Namespace) -> int:
    if sys.version_info < (3, 10):
        print(
            "OpenAlpha requires Python 3.10 or newer. "
            f"Current Python is {sys.version.split()[0]}."
        )
        return 1

    project_root = Path(args.path).resolve()
    frontend_dir = project_root / "frontend"

    if not (project_root / "main.py").exists():
        print(f"Could not find OpenAlpha backend entrypoint at {project_root / 'main.py'}")
        return 1

    if not (frontend_dir / "package.json").exists():
        print(f"Could not find OpenAlpha frontend package at {frontend_dir / 'package.json'}")
        return 1

    npm_command = _npm_command()
    if shutil.which(npm_command) is None:
        print("Could not find npm. Install Node.js, then run npm install in frontend/.")
        return 1

    processes: list[subprocess.Popen[bytes]] = []

    backend_port = _find_available_port(BACKEND_HOST, BACKEND_PORT)
    frontend_port = _find_available_port(FRONTEND_HOST, FRONTEND_PORT)
    backend_url = f"http://{BACKEND_HOST}:{backend_port}"
    frontend_url = f"http://{FRONTEND_HOST}:{frontend_port}"

    env = os.environ.copy()
    env.setdefault("VITE_API_BASE_URL", backend_url)
    env = _prepare_database(project_root=project_root, env=env)

    _print_startup_message(frontend_url=frontend_url, backend_url=backend_url)

    try:
        processes.append(
            subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "main:app",
                    "--reload",
                    "--host",
                    BACKEND_HOST,
                    "--port",
                    str(backend_port),
                ],
                cwd=project_root,
                env=env,
            )
        )
        processes.append(
            subprocess.Popen(
                [
                    npm_command,
                    "run",
                    "dev",
                    "--",
                    "--port",
                    str(frontend_port),
                    "--strictPort",
                ],
                cwd=frontend_dir,
                env=env,
            )
        )

        return _wait_for_processes(processes)
    except KeyboardInterrupt:
        print("\nStopping OpenAlpha...")
        return 130
    finally:
        for process in processes:
            _terminate_process_tree(process)


def _prepare_database(*, project_root: Path, env: dict[str, str]) -> dict[str, str]:
    env.setdefault("DATABASE_URL", _default_database_url(project_root))
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = env["DATABASE_URL"]

    try:
        from backend.app.db.session import init_db

        print("Setting up local database...", flush=True)
        init_db()
        print(
            f"Database ready: {_display_database_url(env['DATABASE_URL'])}",
            flush=True,
        )
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

    return env


def _default_database_url(project_root: Path) -> str:
    database_path = project_root / "openalpha.db"
    return f"sqlite:///{database_path.as_posix()}"


def _display_database_url(database_url: str) -> str:
    sqlite_prefix = "sqlite:///"
    if database_url.startswith(sqlite_prefix):
        return database_url.removeprefix(sqlite_prefix)

    return database_url


def _print_startup_message(*, frontend_url: str, backend_url: str) -> None:
    print("", flush=True)
    print("OpenAlpha is running on this host.", flush=True)
    print(f"Frontend:    {frontend_url}", flush=True)
    print(f"Backend API: {backend_url}", flush=True)
    print(f"Health:      {backend_url}/api/health", flush=True)
    print("", flush=True)
    print("AI stock reports you can audit.", flush=True)
    print("OpenAlpha is a local-first, open-source AI equity research app.", flush=True)
    print(
        "Run investing agents with your own API keys, generate transparent stock "
        "research reports, and track whether the AI's views were right over time.",
        flush=True,
    )
    print(
        "Research and educational purposes only. OpenAlpha is not personalized "
        "financial advice or a recommendation to buy or sell any security.",
        flush=True,
    )
    print("", flush=True)


def _find_available_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 20):
        if _port_is_available(host, port):
            return port
    raise RuntimeError(
        f"Could not find an available port on {host} from "
        f"{preferred_port} to {preferred_port + 19}."
    )


def _port_is_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        return sock.connect_ex((host, port)) != 0


def _wait_for_processes(processes: list[subprocess.Popen[bytes]]) -> int:
    while True:
        for process in processes:
            return_code = process.poll()
            if return_code is not None:
                return return_code
        time.sleep(0.5)


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return

    process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


if __name__ == "__main__":
    raise SystemExit(main())
