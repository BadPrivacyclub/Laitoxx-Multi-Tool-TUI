from __future__ import annotations

import argparse
import os
import platform
import queue
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, replace
from typing import Literal

from laitoxx.core.settings.paths import ROOT_DIR

ROOT = ROOT_DIR
SPINNER = "|/-\\"

InstallerTarget = Literal["windows", "termux", "debian", "unix"]
PlanetOption = Literal["prompt", "yes", "no"]
TermuxTorchOption = Literal["prompt", "none", "tur", "proot"]


@dataclass(frozen=True, slots=True)
class InstallerOptions:
    """Parsed installer options with shortcuts resolved."""

    target: InstallerTarget
    dry_run: bool
    planet: PlanetOption
    termux_torch: TermuxTorchOption
    no_animation: bool


def detect_platform() -> InstallerTarget:
    if os.name == "nt" or platform.system().lower() == "windows":
        return "windows"
    if os.environ.get("PREFIX") and shutil.which("pkg"):
        return "termux"
    if shutil.which("apt-get"):
        return "debian"
    return "unix"


def installer_command(target: InstallerTarget) -> list[str]:
    commands: dict[InstallerTarget, list[str]] = {
        "windows": ["cmd", "/c", "install-windows.bat"],
        "termux": ["bash", "install-termux.sh"],
        "debian": ["bash", "install-debian.sh"],
        "unix": ["bash", "install.sh"],
    }
    return commands[target]


def parse_args(argv: list[str] | None = None) -> InstallerOptions:
    parser = argparse.ArgumentParser(description="Auto-select the Laitoxx installer")
    parser.add_argument(
        "--platform",
        choices=("auto", "windows", "termux", "debian", "unix"),
        default="auto",
        help="Installer target. Default: auto-detect.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the selected installer without running it.",
    )
    planet_group = parser.add_mutually_exclusive_group()
    planet_group.add_argument(
        "--planet",
        choices=("prompt", "yes", "no"),
        default="prompt",
        help="Install optional PlaNet-like/GeoCLIP Photo Geolocation dependencies.",
    )
    planet_group.add_argument(
        "--install-planet",
        action="store_true",
        help="Shortcut for --planet yes.",
    )
    planet_group.add_argument(
        "--skip-planet",
        action="store_true",
        help="Shortcut for --planet no.",
    )
    parser.add_argument(
        "--termux-torch",
        choices=("prompt", "none", "tur", "proot"),
        default="prompt",
        help="PyTorch setup mode for native Termux.",
    )
    parser.add_argument(
        "--no-animation",
        action="store_true",
        help="Run the selected installer without the animated status line.",
    )
    args = parser.parse_args(argv)

    target = detect_platform() if args.platform == "auto" else args.platform
    return InstallerOptions(
        target=target,
        dry_run=args.dry_run,
        planet=_resolve_planet_shortcut(args),
        termux_torch=args.termux_torch,
        no_animation=args.no_animation,
    )


def main(argv: list[str] | None = None) -> int:
    options = parse_args(argv)
    command = installer_command(options.target)
    if not options.dry_run:
        options = resolve_prompted_options(options)

    print_selection(options, command)
    if options.dry_run:
        return 0

    env = installer_env(options)
    if options.no_animation:
        return subprocess.run(command, cwd=ROOT, env=env, check=False).returncode
    return run_with_animation(command, env)


def installer_env(options: InstallerOptions) -> dict[str, str]:
    env = os.environ.copy()
    if options.planet == "yes":
        env["LAITOXX_INSTALL_GEOCLIP"] = "y"
        env["LAITOXX_INSTALL_PLANET"] = "y"
    elif options.planet == "no":
        env["LAITOXX_INSTALL_GEOCLIP"] = "n"
        env["LAITOXX_INSTALL_PLANET"] = "n"

    if options.termux_torch != "prompt":
        env["PHOTO2GEO_TORCH"] = options.termux_torch
    return env


def resolve_prompted_options(options: InstallerOptions) -> InstallerOptions:
    planet = options.planet
    termux_torch = options.termux_torch

    if planet == "prompt":
        if sys.stdin.isatty():
            answer = input("Install optional PlaNet-like/GeoCLIP Photo Geolocation mode? [y/N] ")
            planet = "yes" if answer.strip().lower() == "y" else "no"
        else:
            planet = "no"

    if options.target == "termux" and termux_torch == "prompt":
        if sys.stdin.isatty():
            print(
                "PyTorch is optional and only needed for Netryx indexing or PlaNet-like inference."
            )
            answer = input("Termux PyTorch setup: none/tur/proot [none]: ").strip().lower()
            termux_torch = answer if answer in {"tur", "proot"} else "none"
        else:
            termux_torch = "none"

    return replace(options, planet=planet, termux_torch=termux_torch)


def print_selection(options: InstallerOptions, command: list[str]) -> None:
    print(f"Selected installer: {options.target}")
    print("Command:", " ".join(command))
    if options.planet != "prompt":
        print(f"PlaNet-like/GeoCLIP option: {options.planet}")
    if options.termux_torch != "prompt":
        print(f"Termux PyTorch option: {options.termux_torch}")


def run_with_animation(command: list[str], env: dict[str, str]) -> int:
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=None,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    line_queue: queue.Queue[str] = queue.Queue()
    output_lines: list[str] = []
    last_line = "Starting installer..."

    reader = threading.Thread(
        target=_read_process_output,
        args=(process, line_queue),
        daemon=True,
    )
    reader.start()
    frame = 0

    while process.poll() is None:
        last_line = _drain_lines(line_queue, output_lines, last_line)
        print(
            f"\r{SPINNER[frame % len(SPINNER)]} Installing... {last_line[:96]:<96}",
            end="",
            flush=True,
        )
        frame += 1
        time.sleep(0.12)

    reader.join(timeout=1)
    last_line = _drain_lines(line_queue, output_lines, last_line)
    return _finish_process(process, output_lines, last_line)


def _resolve_planet_shortcut(args: argparse.Namespace) -> PlanetOption:
    if args.install_planet:
        return "yes"
    if args.skip_planet:
        return "no"
    return args.planet


def _read_process_output(
    process: subprocess.Popen[str],
    line_queue: queue.Queue[str],
) -> None:
    if process.stdout is None:
        return
    for line in process.stdout:
        line_queue.put(line)


def _drain_lines(
    line_queue: queue.Queue[str],
    output_lines: list[str],
    last_line: str,
) -> str:
    while True:
        try:
            line = line_queue.get_nowait()
        except queue.Empty:
            return last_line
        output_lines.append(line)
        last_line = line.strip() or last_line


def _finish_process(
    process: subprocess.Popen[str],
    output_lines: list[str],
    last_line: str,
) -> int:
    return_code = int(process.returncode or 0)
    status = "completed" if return_code == 0 else f"failed ({return_code})"
    print(f"\rInstallation {status}: {last_line[:96]:<96}")
    if return_code != 0:
        print("\nInstaller output:")
        print("".join(output_lines))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
