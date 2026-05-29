from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

MIN_READY_BYTES = 10 * 1024 * 1024
DEFAULT_NETRYX_PATH = Path(
    os.environ.get(
        "NETRYX_ASTRA_PATH",
        r"C:\Users\ShShu\Downloads\Netryx-Astra-V2-Geolocation-Tool-main\Netryx-Astra-V2-Geolocation-Tool-main",
    )
)


def resolve_source_path(source_path: str | os.PathLike[str] | None = None) -> Path:
    return Path(source_path or DEFAULT_NETRYX_PATH).expanduser()


def torch_hub_dir() -> Path:
    torch_home = Path(os.environ.get("TORCH_HOME", Path.home() / ".cache" / "torch"))
    return torch_home.expanduser() / "hub"


def megaloc_local_weight_path(source_path: str | os.PathLike[str] | None = None) -> Path:
    return resolve_source_path(source_path) / "megaloc_weights.pth"


def weight_cache_paths(source_path: str | os.PathLike[str] | None = None) -> list[Path]:
    hub_dir = torch_hub_dir()
    return [
        megaloc_local_weight_path(source_path),
        hub_dir / "checkpoints",
        *hub_dir.glob("gmberton_MegaLoc*"),
    ]


def path_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size

    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            try:
                total += file_path.stat().st_size
            except OSError:
                continue
    return total


def weight_cache_size_bytes(source_path: str | os.PathLike[str] | None = None) -> int:
    return sum(path_size_bytes(path) for path in weight_cache_paths(source_path))


def minimal_weights_ready(source_path: str | os.PathLike[str] | None = None) -> bool:
    return any(path_size_bytes(path) >= MIN_READY_BYTES for path in weight_cache_paths(source_path))


def prepare_megaloc_weights(source_path: str | os.PathLike[str] | None = None) -> None:
    source_root = resolve_source_path(source_path)
    if not source_root.is_dir():
        raise FileNotFoundError(f"Netryx Astra source path not found: {source_root}")

    sys.path.insert(0, str(source_root))
    print("Preparing minimal Photo geolocation weights: MegaLoc", flush=True)
    print(f"Netryx source: {source_root}", flush=True)
    print(f"Torch hub cache: {torch_hub_dir()}", flush=True)
    from megaloc_utils import get_megaloc_model

    get_megaloc_model()
    print("MegaLoc weights are ready.", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare Photo geolocation model weights")
    parser.add_argument("--source-path", default="", help="Netryx Astra source directory")
    args = parser.parse_args(argv)

    try:
        prepare_megaloc_weights(args.source_path or None)
    except Exception as exc:
        print(f"Error: {exc}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
