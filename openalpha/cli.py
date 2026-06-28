from __future__ import annotations

import argparse
import os
import shlex
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
PROJECT_VENV_DIRNAME = ".venv"
VENV_REEXEC_ENV_VAR = "OPENALPHA_CLI_REEXEC"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="openalpha",
        description="OpenAlpha local development commands.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    setup_parser = subparsers.add_parser(
        "setup",
        help="Install local OpenAlpha Python and frontend dependencies.",
    )
    setup_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Project root to set up. Defaults to the current directory.",
    )
    setup_parser.add_argument(
        "--dev",
        action="store_true",
        help="Install optional development dependencies as part of setup.",
    )
    setup_parser.set_defaults(func=setup_app)

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


def setup_app(args: argparse.Namespace) -> int:
    resolved = _resolve_project_layout(args.path)
    if resolved is None:
        return 1
    project_root, frontend_dir = resolved

    venv_python = _ensure_project_virtualenv(project_root)
    if venv_python is None:
        return 1

    if not _python_version_supported(python_executable=venv_python):
        return 1

    npm_command = _npm_command()
    if shutil.which(npm_command) is None:
        print("Could not find npm. Install Node.js, then rerun `openalpha setup`.")
        return 1

    editable_target = ".[dev]" if args.dev else "."

    if not _bootstrap_packaging_tools(venv_python, project_root=project_root):
        return 1

    print("Installing Python package into the project virtual environment...", flush=True)
    if not _run_command(
        [str(venv_python), "-m", "pip", "install", "-e", editable_target],
        cwd=project_root,
    ):
        return 1

    print("Installing frontend dependencies...", flush=True)
    if not _run_command([npm_command, "install"], cwd=frontend_dir):
        return 1

    print("", flush=True)
    print("OpenAlpha setup is complete.", flush=True)
    print(f"Run: {_recommended_run_command(project_root)}", flush=True)
    if os.name == "nt":
        print(
            rf"Optional shell activation: {project_root}\.venv\Scripts\Activate.ps1",
            flush=True,
        )
    return 0


def run_app(args: argparse.Namespace) -> int:
    resolved = _resolve_project_layout(args.path)
    if resolved is None:
        return 1
    project_root, frontend_dir = resolved

    reexec_return_code = _maybe_reexec_in_project_venv(command="run", project_root=project_root)
    if reexec_return_code is not None:
        return reexec_return_code

    if not _python_version_supported():
        return 1

    npm_command = _npm_command()
    if shutil.which(npm_command) is None:
        print("Could not find npm. Install Node.js, then run npm install in frontend/.")
        return 1

    if not (frontend_dir / "node_modules").exists():
        print(
            "Frontend dependencies are not installed. "
            "Run `openalpha setup .` first."
        )
        return 1

    processes: list[subprocess.Popen[bytes]] = []

    backend_port = _find_available_port(BACKEND_HOST, BACKEND_PORT)
    frontend_port = _find_available_port(FRONTEND_HOST, FRONTEND_PORT)
    backend_url = f"http://{BACKEND_HOST}:{backend_port}"
    frontend_url = f"http://{FRONTEND_HOST}:{frontend_port}"

    env = os.environ.copy()
    env.setdefault("VITE_API_BASE_URL", backend_url)
    try:
        env = _prepare_database(project_root=project_root, env=env)
    except RuntimeError:
        return 1

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


def _python_version_supported(*, python_executable: Path | None = None) -> bool:
    if python_executable is not None and python_executable.resolve() != Path(sys.executable).resolve():
        completed = subprocess.run(
            [
                str(python_executable),
                "-c",
                "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)",
            ],
            check=False,
        )
        if completed.returncode == 0:
            return True
        print(f"OpenAlpha requires Python 3.10 or newer: {python_executable}")
        return False

    if sys.version_info >= (3, 10):
        return True

    print(
        "OpenAlpha requires Python 3.10 or newer. "
        f"Current Python is {sys.version.split()[0]}."
    )
    return False


def _resolve_project_layout(project_path: str) -> tuple[Path, Path] | None:
    project_root = Path(project_path).resolve()
    frontend_dir = project_root / "frontend"

    if not (project_root / "main.py").exists():
        print(f"Could not find OpenAlpha backend entrypoint at {project_root / 'main.py'}")
        return None

    if not (frontend_dir / "package.json").exists():
        print(f"Could not find OpenAlpha frontend package at {frontend_dir / 'package.json'}")
        return None

    return project_root, frontend_dir


def _ensure_project_virtualenv(project_root: Path) -> Path | None:
    venv_python = _project_venv_python(project_root)
    if venv_python.exists():
        return venv_python

    print(f"Creating local virtual environment at {project_root / PROJECT_VENV_DIRNAME}...", flush=True)
    if not _create_virtualenv(project_root):
        return None
    if not venv_python.exists():
        print(f"Virtual environment was not created successfully: {venv_python}")
        return None
    return venv_python


def _create_virtualenv(project_root: Path) -> bool:
    for command in _venv_creation_commands():
        completed = subprocess.run(command, cwd=project_root, check=False)
        if completed.returncode == 0:
            return True
    print(
        "Could not create the project virtual environment. "
        "Install Python 3.10+ and retry."
    )
    return False


def _bootstrap_packaging_tools(venv_python: Path, *, project_root: Path) -> bool:
    print("Bootstrapping packaging tools in the project virtual environment...", flush=True)
    if not _run_command(
        [str(venv_python), "-m", "ensurepip", "--upgrade"],
        cwd=project_root,
    ):
        return False

    return _run_command(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "pip",
            "setuptools>=68",
            "wheel",
        ],
        cwd=project_root,
    )


def _venv_creation_commands() -> list[list[str]]:
    commands: list[list[str]] = []
    if os.name == "nt" and shutil.which("py") is not None:
        commands.append(["py", "-3.10", "-m", "venv", PROJECT_VENV_DIRNAME])
    commands.append([sys.executable, "-m", "venv", PROJECT_VENV_DIRNAME])
    return commands


def _project_venv_python(project_root: Path) -> Path:
    scripts_dir = "Scripts" if os.name == "nt" else "bin"
    executable_name = "python.exe" if os.name == "nt" else "python"
    return project_root / PROJECT_VENV_DIRNAME / scripts_dir / executable_name


def _maybe_reexec_in_project_venv(*, command: str, project_root: Path) -> int | None:
    if os.environ.get(VENV_REEXEC_ENV_VAR) == "1":
        return None

    venv_python = _project_venv_python(project_root)
    if not venv_python.exists():
        return None
    if venv_python.resolve() == Path(sys.executable).resolve():
        return None

    env = os.environ.copy()
    env[VENV_REEXEC_ENV_VAR] = "1"
    return subprocess.run(
        [str(venv_python), "-m", "openalpha.cli", command, str(project_root)],
        cwd=project_root,
        env=env,
        check=False,
    ).returncode


def _prepare_database(*, project_root: Path, env: dict[str, str]) -> dict[str, str]:
    env.setdefault("DATABASE_URL", _default_database_url(project_root))
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = env["DATABASE_URL"]

    try:
        try:
            from backend.app.db.session import init_db
        except ModuleNotFoundError as exc:
            print(
                "OpenAlpha dependencies are not installed for this interpreter. "
                "Run `py -m openalpha setup .` first."
            )
            raise RuntimeError("missing runtime dependencies") from exc

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


def _run_command(command: list[str], *, cwd: Path) -> bool:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode == 0:
        return True

    print(
        f"Command failed with exit code {completed.returncode}: "
        f"{_format_command(command)}"
    )
    return False


def _format_command(command: list[str]) -> str:
    if os.name == "nt":
        return subprocess.list2cmdline(command)
    return shlex.join(command)


def _recommended_run_command(project_root: Path) -> str:
    if Path.cwd().resolve() == project_root:
        return "py -m openalpha run ."
    return f"Activate {project_root / PROJECT_VENV_DIRNAME / 'Scripts' / 'Activate.ps1'} and run `openalpha run {project_root}`"


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


if __name__ == "__main__":
    raise SystemExit(main())
