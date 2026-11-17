"""Unified DocuLens Control Script: setup, health check, local run, Docker, and Docker Compose.

Run interactively:
    python run_doculens.py

Or pass an action directly:
    python run_doculens.py setup      # Prepare .env, venv/dependencies, data dir (starts nothing)
    python run_doculens.py check      # Verify environment, files, Docker, JS & Python tests
    python run_doculens.py local      # Setup (if needed) and start locally on http://127.0.0.1:8000
    python run_doculens.py docker     # Build Docker image and run DocuLens container
    python run_doculens.py compose    # Run full stack (API + Ollama) via Docker Compose
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMAGE_TAG = "doculens-api:0.2.0"
CONTAINER_NAME = "doculens-app"
DEFAULT_PORT = "8000"


def resolve_port(cli_port: int | None = None) -> str:
    """Resolve port from CLI --port, env var DOCULENS_PORT, .env file, or DEFAULT_PORT."""
    if cli_port is not None:
        return str(cli_port)
    env_val = os.environ.get("DOCULENS_PORT", "").strip()
    if env_val.isdigit():
        return env_val
    env_file = ROOT / ".env"
    if env_file.is_file():
        try:
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                k, v = stripped.split("=", 1)
                if k.strip() == "DOCULENS_PORT":
                    val = v.strip().strip("\"'")
                    if val.isdigit():
                        return val
        except OSError:
            pass
    return DEFAULT_PORT


def _clean_zone_identifiers() -> int:
    removed = 0
    for path in ROOT.rglob("*"):
        if path.is_file() and path.name.lower().endswith("zone.identifier"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def _venv_python() -> Path:
    if os.name == "nt":
        return ROOT / "doculens" / "Scripts" / "python.exe"
    return ROOT / "doculens" / "bin" / "python"


def _candidate_base_pythons() -> list[str]:
    candidates: list[str] = []
    if sys.version_info >= (3, 12):
        candidates.append(sys.executable)
    if os.name == "nt":
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            py312 = Path(local_app) / "Programs" / "Python" / "Python312" / "python.exe"
            if py312.is_file():
                candidates.append(str(py312))
        py_launcher = shutil.which("py")
        if py_launcher:
            try:
                out = subprocess.check_output(
                    [py_launcher, "-3.12", "-c", "import sys; print(sys.executable)"],
                    text=True,
                    stderr=subprocess.DEVNULL,
                ).strip()
                if out:
                    candidates.append(out)
            except Exception:
                pass
    for name in ("python3.12", "python3", "python"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        norm = str(Path(c).resolve()) if Path(c).exists() else c
        if norm not in seen:
            seen.add(norm)
            unique.append(c)
    return unique


def _python_has_runtime(python_bin: str) -> bool:
    code = (
        "import importlib.util as u; "
        "pkgs = ['fastapi', 'uvicorn', 'pydantic', 'pydantic_settings', 'fitz', 'numpy', 'faiss', 'sentence_transformers']; "
        "has_http = bool(u.find_spec('httpx') or u.find_spec('httpx2')); "
        "ok = has_http and all(bool(u.find_spec(p)) for p in pkgs); "
        "raise SystemExit(0 if ok else 1)"
    )
    return (
        subprocess.run(
            [python_bin, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )


def find_best_python() -> str:
    venv_py = _venv_python()
    if venv_py.is_file() and _python_has_runtime(str(venv_py)):
        return str(venv_py)
    for cand in _candidate_base_pythons():
        if _python_has_runtime(cand):
            return cand
    if venv_py.is_file():
        return str(venv_py)
    cands = _candidate_base_pythons()
    return cands[0] if cands else sys.executable


def _ensure_httpx_shim(python_bin: str) -> bool:
    """Create a tiny site-packages bridge if httpx2 is installed without httpx."""
    probe = (
        "import importlib.util as u, sysconfig; "
        "print('1' if (not u.find_spec('httpx') and u.find_spec('httpx2')) else '0'); "
        "print(sysconfig.get_paths().get('purelib', ''))"
    )
    res = subprocess.run([python_bin, "-c", probe], capture_output=True, text=True)
    if res.returncode != 0:
        return False
    lines = res.stdout.strip().splitlines()
    if len(lines) < 2 or lines[0] != "1" or not lines[1]:
        return False
    shim_init = Path(lines[1]) / "httpx" / "__init__.py"
    if shim_init.is_file():
        return False
    try:
        shim_init.parent.mkdir(parents=True, exist_ok=True)
        shim_init.write_text(
            "import sys as _sys\n"
            "_sys.modules.pop('httpx', None)\n"
            "_sys.modules.pop('httpcore', None)\n"
            "import httpx2 as _httpx2\n"
            "_httpx2.alias_httpx()\n"
            "from httpx2 import *\n",
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def cmd_setup(*, install_deps: bool = True) -> int:
    """Prepare .env, data/, and Python runtime without starting any server."""
    os.chdir(ROOT)
    print("\n=== DocuLens Setup (No Services Started) ===")

    cleaned = _clean_zone_identifiers()
    if cleaned:
        print(f"[ok] Cleaned {cleaned} Zone.Identifier sidecar file(s)")

    env_file = ROOT / ".env"
    env_example = ROOT / ".env.example"
    if not env_file.is_file() and env_example.is_file():
        shutil.copyfile(env_example, env_file)
        print("[ok] Created .env from .env.example")
    elif env_file.is_file():
        print("[ok] Configuration .env already present")
    else:
        print("[warn] .env.example not found")

    (ROOT / "data").mkdir(parents=True, exist_ok=True)
    print("[ok] Data directory ready")

    python_bin = find_best_python()
    venv_py = _venv_python()
    has_runtime = _python_has_runtime(python_bin)

    if install_deps and not has_runtime:
        uv_bin = shutil.which("uv")
        if uv_bin:
            print("[..] Installing dependencies via uv into ./doculens ...")
            env = {**os.environ, "UV_PROJECT_ENVIRONMENT": str(ROOT / "doculens")}
            subprocess.run([uv_bin, "python", "install", "3.12"], check=False, env=env)
            subprocess.run([uv_bin, "venv", "doculens", "--python", "3.12"], check=True, env=env)
            sync_cmd = [uv_bin, "sync", "--locked", "--dev"] if (ROOT / "uv.lock").is_file() else [uv_bin, "sync"]
            subprocess.run(sync_cmd, check=True, env=env)
            python_bin = str(venv_py)
            has_runtime = _python_has_runtime(python_bin)
        elif not venv_py.is_file():
            base = find_best_python()
            print(f"[..] Creating ./doculens virtual environment using {base} ...")
            subprocess.run([base, "-m", "venv", str(ROOT / "doculens"), "--system-site-packages"], check=False)
            if venv_py.is_file():
                python_bin = str(venv_py)
                has_runtime = _python_has_runtime(python_bin)

    if _ensure_httpx_shim(python_bin):
        print("[ok] Configured httpx2 compatibility bridge")

    if has_runtime:
        print(f"[ok] Python runtime verified: {python_bin}")
    else:
        print(
            "[warn] Core Python packages (FastAPI/PyMuPDF/FAISS/Sentence-Transformers) "
            f"not detected in {python_bin}. Install 'uv' and re-run setup, or use Docker / Compose."
        )

    print("[done] Setup complete. Nothing was started.")
    return 0


def _port_in_use(port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            return sock.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False


def cmd_check(*, full: bool = False) -> int:
    """Verify workspace files, Python packages, Docker, and automated tests."""
    os.chdir(ROOT)
    print("\n=== DocuLens System & Project Check ===")
    failures = 0

    required_files = [
        "app/main.py",
        "app/adapters/llm/multi_provider_client.py",
        "app/services/provider_registry.py",
        "frontend/index.html",
        "frontend/src/main.js",
        "pyproject.toml",
        ".env.example",
        "Dockerfile",
        "compose.yaml",
    ]
    missing = [f for f in required_files if not (ROOT / f).exists()]
    if missing:
        print(f"[FAIL] Missing required files: {', '.join(missing)}")
        failures += 1
    else:
        print(f"[PASS] All {len(required_files)} core project files present")

    python_bin = find_best_python()
    print(f"[INFO] Active Python: {python_bin}")

    deps_code = (
        "import importlib.util as u; "
        "req = ['fastapi', 'uvicorn', 'pydantic', 'pydantic_settings', 'fitz', 'numpy', 'faiss', 'sentence_transformers']; "
        "missing = [m for m in req if not u.find_spec(m)]; "
        "missing += [] if (u.find_spec('httpx') or u.find_spec('httpx2')) else ['httpx']; "
        "print(','.join(missing)); "
        "raise SystemExit(1 if missing else 0)"
    )
    dep_res = subprocess.run([python_bin, "-c", deps_code], capture_output=True, text=True)
    if dep_res.returncode == 0:
        print("[PASS] Required Python dependencies installed")
    else:
        print(f"[FAIL] Missing Python dependencies: {dep_res.stdout.strip()}")
        failures += 1

    # Docker / Compose availability check (informational if running locally only)
    docker_bin = shutil.which("docker")
    if docker_bin:
        info_res = subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        comp_res = subprocess.run(
            [docker_bin, "compose", "version"],
            capture_output=True,
            text=True,
        )
        if info_res.returncode == 0:
            print("[PASS] Docker daemon is running")
        else:
            print("[WARN] Docker CLI found, but Docker daemon is not running (needed for docker/compose modes)")
        if comp_res.returncode == 0:
            cfg_res = subprocess.run(
                [docker_bin, "compose", "config", "-q"],
                capture_output=True,
                text=True,
            )
            if cfg_res.returncode == 0:
                print("[PASS] compose.yaml validated cleanly")
            else:
                print(f"[FAIL] compose.yaml validation error: {cfg_res.stderr.strip()}")
                failures += 1
    else:
        print("[WARN] Docker CLI not installed (local mode still works)")

    port = int(resolve_port())
    if _port_in_use(port):
        print(f"[INFO] Port {port} is currently listening")
    else:
        print(f"[PASS] Port {port} is free and ready")

    # Frontend JS syntax + Node tests
    node_bin = shutil.which("node")
    if node_bin:
        js_files = [
            str(p)
            for p in sorted((ROOT / "frontend" / "src").rglob("*.js"))
        ]
        syntax_ok = True
        for js in js_files:
            if subprocess.run([node_bin, "--check", js], stderr=subprocess.PIPE).returncode != 0:
                print(f"[FAIL] JS syntax check failed: {js}")
                syntax_ok = False
                failures += 1
        if syntax_ok:
            print(f"[PASS] All {len(js_files)} frontend JS files passed syntax check")
        mod_test = ROOT / "tests" / "web" / "modules.test.cjs"
        if mod_test.is_file():
            nt = subprocess.run([node_bin, "--test", str(mod_test)], capture_output=True, text=True)
            if nt.returncode == 0:
                print("[PASS] Frontend module tests passed")
            else:
                print(f"[FAIL] Frontend module tests failed:\n{nt.stdout}\n{nt.stderr}")
                failures += 1
    else:
        print("[WARN] Node.js not found — skipped JS checks")

    # Python tests
    has_pytest = (
        subprocess.run(
            [python_bin, "-c", "import importlib.util; raise SystemExit(0 if importlib.util.find_spec('pytest') else 1)"]
        ).returncode
        == 0
    )
    if has_pytest:
        test_targets = (
            ["tests"]
            if full
            else [
                "tests/product/test_multi_provider_and_intelligence.py",
                "tests/phase3/test_answer_schema.py",
            ]
        )
        existing_targets = [t for t in test_targets if (ROOT / t).exists()]
        if existing_targets:
            pt = subprocess.run(
                [python_bin, "-m", "pytest", *existing_targets, "-q"],
                capture_output=True,
                text=True,
            )
            if pt.returncode == 0:
                summary = pt.stdout.strip().splitlines()[-1] if pt.stdout.strip() else "passed"
                print(f"[PASS] Python tests: {summary}")
            else:
                print(f"[FAIL] Python tests failed:\n{pt.stdout}\n{pt.stderr}")
                failures += 1
    else:
        print("[WARN] pytest not installed — skipped Python test run")

    print("")
    if failures == 0:
        print("[OK] Everything looks healthy and ready!")
        return 0
    print(f"[ERROR] Check finished with {failures} failure(s).")
    return 1


def _open_when_ready(url: str) -> None:
    def _worker() -> None:
        health_url = f"{url}/health"
        for _ in range(30):
            try:
                with urllib.request.urlopen(health_url, timeout=1.0) as resp:
                    if resp.status == 200:
                        try:
                            is_wsl = False
                            if os.name != "nt" and Path("/proc/version").is_file():
                                is_wsl = "microsoft" in Path("/proc/version").read_text(
                                    encoding="utf-8", errors="ignore"
                                ).lower()
                            if is_wsl:
                                wslview = shutil.which("wslview")
                                if wslview:
                                    subprocess.Popen([wslview, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            else:
                                webbrowser.open(url)
                        except Exception:
                            pass
                        return
            except (urllib.error.URLError, TimeoutError, OSError):
                time.sleep(0.75)

    threading.Thread(target=_worker, daemon=True).start()


def cmd_local(*, open_browser: bool = True, port_override: int | None = None) -> int:
    """Prepare environment if needed and run DocuLens locally."""
    cmd_setup(install_deps=False)
    python_bin = find_best_python()
    if not _python_has_runtime(python_bin):
        cmd_setup(install_deps=True)
        python_bin = find_best_python()

    port = resolve_port(port_override)
    url = f"http://127.0.0.1:{port}"
    print(f"\n[DocuLens] Starting local server at {url}")
    print("[DocuLens] Press Ctrl+C to stop.\n")
    if open_browser:
        _open_when_ready(url)

    return subprocess.call(
        [
            python_bin,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
        ]
    )


def _require_docker_daemon() -> str:
    docker_bin = shutil.which("docker")
    if not docker_bin:
        raise RuntimeError("Docker CLI not found. Install Docker Desktop / Docker Engine first.")
    if (
        subprocess.run(
            [docker_bin, "info"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        != 0
    ):
        raise RuntimeError("Docker daemon is not running. Start Docker Desktop / Docker service first.")
    return docker_bin


def cmd_docker(*, detach: bool = False, stop: bool = False, open_browser: bool = True, port_override: int | None = None) -> int:
    """Build and run DocuLens as a standalone Docker container."""
    os.chdir(ROOT)
    try:
        docker_bin = _require_docker_daemon()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if stop:
        return subprocess.call([docker_bin, "rm", "-f", CONTAINER_NAME])

    cmd_setup(install_deps=False)
    port = resolve_port(port_override)
    url = f"http://127.0.0.1:{port}"

    print(f"\n[DocuLens] Building Docker image {IMAGE_TAG} ...")
    build_rc = subprocess.call([docker_bin, "build", "-t", IMAGE_TAG, "."])
    if build_rc != 0:
        return build_rc

    subprocess.run(
        [docker_bin, "rm", "-f", CONTAINER_NAME],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    run_cmd = [
        docker_bin,
        "run",
        "--name",
        CONTAINER_NAME,
        "-p",
        f"127.0.0.1:{port}:8000",
        "-v",
        "doculens-models:/models",
        "-v",
        "doculens-data:/app/data",
    ]
    if (ROOT / ".env").is_file():
        run_cmd.extend(["--env-file", ".env"])
    if detach:
        run_cmd.append("-d")
    else:
        run_cmd.append("--rm")
    run_cmd.append(IMAGE_TAG)

    print(f"[DocuLens] Starting container at {url} ...")
    if open_browser:
        _open_when_ready(url)
    return subprocess.call(run_cmd)


def cmd_compose(*, detach: bool = False, down: bool = False, open_browser: bool = True, port_override: int | None = None) -> int:
    """Run the full DocuLens + Ollama stack via Docker Compose."""
    os.chdir(ROOT)
    try:
        docker_bin = _require_docker_daemon()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if down:
        return subprocess.call([docker_bin, "compose", "down"])

    cmd_setup(install_deps=False)
    port = resolve_port(port_override)
    url = f"http://127.0.0.1:{port}"
    env = {**os.environ, "DOCULENS_PORT": port}
    up_cmd = [docker_bin, "compose", "up", "--build"]
    if detach:
        up_cmd.append("-d")

    print(f"\n[DocuLens] Launching Docker Compose stack at {url} ...")
    if open_browser:
        _open_when_ready(url)
    return subprocess.call(up_cmd, env=env)


def interactive_menu() -> int:
    while True:
        port = resolve_port()
        print("\n====================================================")
        print("  DocuLens Control Script (All-in-One Launcher)")
        print("====================================================")
        print(f"  [1] Run Locally              (http://127.0.0.1:{port})")
        print("  [2] Run with Docker          (Standalone container)")
        print("  [3] Run with Docker Compose  (API + Ollama stack)")
        print("  [4] Setup Only               (Prepare .env/venv, start nothing)")
        print("  [5] Check Everything         (Verify deps, Docker & tests)")
        print("  [6] Stop Docker / Compose    (Clean stop containers)")
        print("  [0] Exit")
        choice = input("\nSelect an option [1-6, 0]: ").strip()
        if choice == "1":
            return cmd_local()
        if choice == "2":
            return cmd_docker()
        if choice == "3":
            return cmd_compose()
        if choice == "4":
            cmd_setup(install_deps=True)
        elif choice == "5":
            cmd_check()
        elif choice == "6":
            docker_bin = shutil.which("docker")
            if docker_bin:
                subprocess.run([docker_bin, "rm", "-f", CONTAINER_NAME], stderr=subprocess.DEVNULL)
                subprocess.run([docker_bin, "compose", "down"], stderr=subprocess.DEVNULL)
            print("[ok] Stopped any running DocuLens Docker / Compose containers.")
        elif choice == "0":
            return 0
        else:
            print("Invalid choice. Enter 0-6.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Unified DocuLens setup, diagnostics, local server, Docker, and Compose launcher."
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=["local", "docker", "compose", "setup", "check", "stop"],
        help="Action to perform (omit for interactive menu)",
    )
    parser.add_argument("-d", "--detach", action="store_true", help="Run Docker/Compose in background")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    parser.add_argument("--full", action="store_true", help="Run full pytest suite during 'check'")
    parser.add_argument("--port", type=int, default=None, help="Override port (defaults to DOCULENS_PORT in .env or 8000)")
    args = parser.parse_args()

    if args.action is None:
        return interactive_menu()
    if args.action == "setup":
        return cmd_setup(install_deps=True)
    if args.action == "check":
        return cmd_check(full=args.full)
    if args.action == "local":
        return cmd_local(open_browser=not args.no_browser, port_override=args.port)
    if args.action == "docker":
        return cmd_docker(detach=args.detach, open_browser=not args.no_browser, port_override=args.port)
    if args.action == "compose":
        return cmd_compose(detach=args.detach, open_browser=not args.no_browser, port_override=args.port)
    if args.action == "stop":
        cmd_docker(stop=True)
        return cmd_compose(down=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
