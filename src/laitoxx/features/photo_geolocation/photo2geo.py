from __future__ import annotations

import argparse
import ast
import importlib
import importlib.util
import json
import os
import re
import sys
import tempfile
import time
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from laitoxx.core.settings.paths import ROOT_DIR
from laitoxx.features.photo_geolocation.photo2geo_backend import (
    build_compact_index,
    get_index_dir,
    merge_compact_indexes,
    search_compact_index,
)

DEFAULT_NETRYX_PATH = Path(
    os.environ.get(
        "NETRYX_ASTRA_PATH",
        r"C:\Users\ShShu\Downloads\Netryx-Astra-V2-Geolocation-Tool-main\Netryx-Astra-V2-Geolocation-Tool-main",
    )
)

NETRYX_MODULES = ("megaloc_utils", "mast3r_utils", "netryx_hub")
OPTIONAL_DEPENDENCIES = (
    "aiohttp",
    "cv2",
    "einops",
    "huggingface_hub",
    "matplotlib",
    "numpy",
    "PIL",
    "safetensors",
    "sklearn",
    "timm",
    "torch",
    "torchvision",
)
GEOCLIP_DEPENDENCIES = ("geoclip", "torch", "PIL", "numpy")
RESULT_MARKER = "__LAITOXX_PHOTO_GEOLOCATION_RESULT_JSON__="
PROGRESS_MARKER = "__LAITOXX_PHOTO_GEOLOCATION_PROGRESS_JSON__="
DOWNLOAD_CHUNK_SIZE = 1024 * 1024
PROJECT_ROOT = ROOT_DIR
DEFAULT_PLANET_MODEL_DIR = Path(
    os.environ.get(
        "LAITOXX_PLANET_MODEL_DIR",
        PROJECT_ROOT / "models" / "photo_geolocation" / "planet",
    )
).expanduser()


@dataclass(frozen=True)
class NetryxSource:
    root: Path

    @property
    def index_dir(self) -> Path:
        return get_index_dir(self.root)

    def module_path(self, module_name: str) -> Path:
        return self.root / f"{module_name}.py"


def photo2geo_tool(config: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Run Photo geolocation actions from the Laitoxx TUI."""
    config = _normalize_config(config or _read_interactive_config())
    engine = str(config.get("engine") or "netryx").strip().lower()
    mode = str(config.get("mode") or "status").strip().lower()

    if engine == "geoclip":
        if mode == "status":
            return _print_geoclip_status()
        if mode == "search":
            return _search_photo_geoclip(config)
        print(f"Error: GeoCLIP mode does not support Photo geolocation action: {mode}")
        return None

    source = NetryxSource(Path(config.get("source_path") or DEFAULT_NETRYX_PATH).expanduser())
    if mode == "status":
        return _print_status(source)
    if mode == "search":
        return _search_photo(source, config)
    if mode == "create_index":
        return _create_local_index(source, config)
    if mode == "build_index":
        return _build_compact_index(source)
    if mode == "hub_list":
        return _hub_list(source)
    if mode == "hub_search":
        return _hub_search(source, config)
    if mode == "hub_download":
        return _hub_download(source, config)
    if mode == "hub_download_all":
        return _hub_download_all(source, config)
    if mode == "import_bundle":
        return _import_bundle(source, config)
    if mode == "export_bundle":
        return _export_bundle(source, config)

    print(f"Error: unsupported Photo geolocation mode: {mode}")
    return None


def _normalize_config(config: dict[str, Any]) -> dict[str, Any]:
    """Accept both advanced Netryx fields and the simplified TUI form."""
    normalized = dict(config)
    engine_aliases = {
        "": "netryx",
        "netryx_astra": "netryx",
        "astra": "netryx",
        "local": "netryx",
        "global": "geoclip",
        "planet": "geoclip",
        "planet_like": "geoclip",
        "geoclip_planet": "geoclip",
        "geoclip-ai": "geoclip",
    }
    raw_engine = str(normalized.get("engine") or "netryx").strip().lower()
    normalized["engine"] = engine_aliases.get(raw_engine, raw_engine)

    task = str(normalized.get("task") or normalized.get("mode") or "status").strip().lower()
    task_aliases = {
        "check_setup": "status",
        "status": "status",
        "search": "search",
        "find_photo": "search",
        "create_index": "create_index",
        "build_index": "build_index",
        "hub_list": "hub_list",
        "hub_search": "hub_search",
        "search_hub": "hub_search",
        "hub_download": "hub_download",
        "download_index": "hub_download",
        "hub_download_all": "hub_download_all",
        "import_bundle": "import_bundle",
        "import_index": "import_bundle",
        "export_bundle": "export_bundle",
        "export_index": "export_bundle",
        "geoclip_status": "status",
        "geoclip_find": "search",
        "planet_find": "search",
    }
    mode = task_aliases.get(task, task)
    normalized["mode"] = mode

    if task in {"geoclip_status", "geoclip_find", "planet_find"}:
        normalized["engine"] = "geoclip"

    target = str(normalized.get("target") or "").strip()
    if target:
        if mode == "search" and not normalized.get("image_path"):
            normalized["image_path"] = target
        elif mode == "hub_search" and not normalized.get("city"):
            normalized["city"] = target
        elif mode == "hub_download" and not normalized.get("repo_id"):
            normalized["repo_id"] = target
        elif mode in {"import_bundle", "export_bundle"} and not normalized.get("bundle_path"):
            normalized["bundle_path"] = target

    location = _parse_location_hint(normalized.get("location_hint"))
    if location:
        lat, lon, radius = location
        normalized.setdefault("center_lat", lat)
        normalized.setdefault("center_lon", lon)
        normalized.setdefault("radius_km", radius)

    return normalized


def _parse_location_hint(value: Any) -> tuple[str, str, str] | None:
    text = str(value or "").strip()
    if not text:
        return None
    parts = [part for part in re.split(r"[,;\s]+", text) if part]
    if len(parts) < 2:
        return None
    lat = parts[0]
    lon = parts[1]
    radius = parts[2] if len(parts) >= 3 else "1"
    return lat, lon, radius


def _print_status(source: NetryxSource) -> dict[str, Any]:
    print("Photo geolocation / Netryx Astra adapter")
    print("Engine: Netryx Astra local/community index")
    print(f"Source path: {source.root}")
    print(f"Exists: {'yes' if source.root.is_dir() else 'no'}")
    print()

    modules = _discover_module_functions(source)
    print("Imported Netryx modules and callable surface:")
    for module_name in NETRYX_MODULES:
        functions = modules.get(module_name, [])
        state = "found" if source.module_path(module_name).exists() else "missing"
        print(f"- {module_name}: {state}, {len(functions)} functions/classes")
        if functions:
            print("  " + ", ".join(functions[:24]))
            if len(functions) > 24:
                print(f"  ... +{len(functions) - 24} more")

    print()
    print("Python dependencies:")
    dependency_state = {}
    for name in OPTIONAL_DEPENDENCIES:
        available = importlib.util.find_spec(name) is not None
        dependency_state[name] = available
        print(f"- {name}: {'ok' if available else 'missing'}")

    index_files = {
        "descriptors": source.index_dir / "megaloc_descriptors.npy",
        "metadata": source.index_dir / "metadata.npz",
        "pca": source.index_dir / "megaloc_pca.pkl",
        "manifest": source.index_dir / "manifest.json",
    }
    print()
    print("Index files:")
    for label, file_path in index_files.items():
        print(f"- {label}: {'found' if file_path.exists() else 'missing'} ({file_path})")

    return {
        "engine": "netryx",
        "source_path": str(source.root),
        "modules": modules,
        "dependencies": dependency_state,
        "index_dir": str(source.index_dir),
    }


def _print_geoclip_status() -> dict[str, Any]:
    model_dir = DEFAULT_PLANET_MODEL_DIR
    model_state = _planet_model_cache_state(model_dir)
    print("Photo geolocation / PlaNet-like global model")
    print("Engine: PlaNet-like worldwide prediction via GeoCLIP")
    print()
    print(
        "This is the Laitoxx PlaNet-like mode backed by the open GeoCLIP package, "
        "not Google's original private PlaNet weights."
    )
    print(f"Project model folder: {model_dir}")
    print(f"Folder exists: {'yes' if model_state['exists'] else 'no'}")
    print(f"Model/cache files: {model_state['file_count']}")
    print(f"Model/cache size: {_format_bytes(model_state['size_bytes'])}")
    print(f"Installed in project folder: {'yes' if model_state['installed'] else 'no'}")
    print()
    print("Python dependencies:")
    dependency_state = {}
    for name in GEOCLIP_DEPENDENCIES:
        available = importlib.util.find_spec(name) is not None
        dependency_state[name] = available
        print(f"- {name}: {'ok' if available else 'missing'}")
    print()
    print("Runtime notes:")
    print("- First run may download GeoCLIP weights.")
    print("- Downloads are directed to the project model folder above.")
    print("- CPU inference works but can be slow; CUDA is used only when available.")
    print("- On Termux, prefer TUR/proot PyTorch or ONNX/mobile-weight workflows.")
    return {
        "engine": "geoclip",
        "model_dir": str(model_dir),
        "model_state": model_state,
        "dependencies": dependency_state,
    }


def _search_photo(source: NetryxSource, config: dict[str, Any]) -> dict[str, Any] | None:
    image_path = Path(str(config.get("image_path") or "")).expanduser()
    if not image_path.is_file():
        print(f"Error: image file not found: {image_path}")
        return None

    center = (_to_float(config.get("center_lat"), 0.0), _to_float(config.get("center_lon"), 0.0))
    radius_km = _bounded_float(config.get("radius_km"), 1.0, minimum=0.1, maximum=100.0)
    top_k = _bounded_int(config.get("top_k"), 25, minimum=1, maximum=500)

    with _netryx_imports(source):
        from megaloc_utils import extract_megaloc_descriptor, load_pca
        from PIL import Image

        pca_path = source.index_dir / "megaloc_pca.pkl"
        if pca_path.exists():
            load_pca(str(pca_path))

        print(f"Loading query image: {image_path}")
        image = Image.open(image_path).convert("RGB")
        print("Extracting MegaLoc descriptor...")
        descriptor = extract_megaloc_descriptor(image, apply_pca_reduction=True)
        print(
            f"Searching compact index around lat={center[0]:.6f}, "
            f"lon={center[1]:.6f}, radius={radius_km:g}km, top_k={top_k}..."
        )
        results = search_compact_index(
            descriptor,
            center,
            radius_km,
            index_dir=source.index_dir,
            top_k=top_k,
        )

    _print_search_results(results)
    return {
        "engine": "netryx",
        "image_path": str(image_path),
        "center": center,
        "radius_km": radius_km,
        "results": results,
    }


def _search_photo_geoclip(config: dict[str, Any]) -> dict[str, Any] | None:
    image_path = Path(str(config.get("image_path") or "")).expanduser()
    if not image_path.is_file():
        print(f"Error: image file not found: {image_path}")
        return None

    model_dir = _prepare_planet_model_dir(config.get("model_dir"))
    top_k = _bounded_int(config.get("top_k"), 5, minimum=1, maximum=50)
    device_choice = str(config.get("model_device") or "auto").strip().lower()
    precision = str(config.get("precision") or "auto").strip().lower()

    try:
        import torch
        from geoclip import GeoCLIP
        from PIL import Image
    except ImportError as exc:
        print(f"Error: GeoCLIP dependency is missing: {exc}")
        print("Install optional GeoCLIP dependencies with requirements-photo2geo-geoclip.txt.")
        return None

    device = _resolve_geoclip_device(torch, device_choice)
    print(f"Using project model folder: {model_dir}")
    print("Loading PlaNet-like GeoCLIP global model...")
    model = GeoCLIP()
    _configure_geoclip_model(model, torch, device, precision)
    if hasattr(model, "eval"):
        model.eval()

    print(f"Runtime: device={device}, precision={precision}")
    print(f"Loading query image: {image_path}")
    image = Image.open(image_path).convert("RGB")
    print(f"Predicting worldwide GPS candidates, top_k={top_k}...")
    with torch.no_grad():
        try:
            top_pred_gps, top_pred_prob = model.predict(image, top_k=top_k)
        except TypeError:
            top_pred_gps, top_pred_prob = model.predict(str(image_path), top_k=top_k)

    results = _geoclip_predictions_to_results(top_pred_gps, top_pred_prob, top_k)
    _print_geoclip_results(results)
    return {
        "engine": "geoclip",
        "image_path": str(image_path),
        "top_k": top_k,
        "device": device,
        "precision": precision,
        "model_dir": str(model_dir),
        "results": results,
    }


def _prepare_planet_model_dir(value: Any = None) -> Path:
    model_dir = Path(str(value or DEFAULT_PLANET_MODEL_DIR)).expanduser()
    cache_dir = model_dir / "cache"
    hf_home = cache_dir / "huggingface"
    torch_home = cache_dir / "torch"
    xdg_cache = cache_dir / "xdg"
    for path in (model_dir, cache_dir, hf_home, torch_home, xdg_cache):
        path.mkdir(parents=True, exist_ok=True)

    os.environ["LAITOXX_PLANET_MODEL_DIR"] = str(model_dir)
    os.environ["HF_HOME"] = str(hf_home)
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(hf_home / "hub")
    os.environ["TORCH_HOME"] = str(torch_home)
    os.environ["XDG_CACHE_HOME"] = str(xdg_cache)
    return model_dir


def _planet_model_cache_state(model_dir: Path | None = None) -> dict[str, Any]:
    model_dir = Path(model_dir or DEFAULT_PLANET_MODEL_DIR).expanduser()
    if not model_dir.exists():
        return {
            "exists": False,
            "installed": False,
            "file_count": 0,
            "model_file_count": 0,
            "size_bytes": 0,
        }

    file_count = 0
    size_bytes = 0
    model_suffixes = {".bin", ".pt", ".pth", ".safetensors", ".onnx", ".pkl", ".npz", ".npy"}
    model_file_count = 0
    for item in model_dir.rglob("*"):
        if not item.is_file():
            continue
        file_count += 1
        with suppress(OSError):
            size_bytes += item.stat().st_size
        if item.suffix.lower() in model_suffixes:
            model_file_count += 1

    return {
        "exists": True,
        "installed": model_file_count > 0,
        "file_count": file_count,
        "model_file_count": model_file_count,
        "size_bytes": size_bytes,
    }


def _resolve_geoclip_device(torch_module: Any, choice: str) -> str:
    if choice == "cuda":
        return "cuda" if torch_module.cuda.is_available() else "cpu"
    if choice == "cpu":
        return "cpu"
    return "cuda" if torch_module.cuda.is_available() else "cpu"


def _configure_geoclip_model(model: Any, torch_module: Any, device: str, precision: str) -> None:
    dtype = None
    if precision in {"float16", "fp16"}:
        dtype = torch_module.float16
    elif precision in {"bfloat16", "bf16"}:
        dtype = torch_module.bfloat16
    elif precision in {"float32", "fp32"}:
        dtype = torch_module.float32

    if not hasattr(model, "to"):
        return
    try:
        if dtype is None:
            model.to(device)
        else:
            model.to(device=device, dtype=dtype)
    except Exception as exc:
        print(f"Warning: could not apply requested GeoCLIP runtime options: {exc}")
        model.to(device)


def _geoclip_predictions_to_results(
    top_pred_gps: Any, top_pred_prob: Any, top_k: int
) -> list[dict[str, Any]]:
    gps_values = _tensor_like_to_list(top_pred_gps)
    prob_values = _tensor_like_to_list(top_pred_prob)
    results = []
    for index, gps in enumerate(gps_values[:top_k]):
        if not isinstance(gps, (list, tuple)) or len(gps) < 2:
            continue
        probability = prob_values[index] if index < len(prob_values) else None
        results.append(
            {
                "rank": index + 1,
                "lat": float(gps[0]),
                "lon": float(gps[1]),
                "probability": None if probability is None else float(probability),
                "map_url": f"https://www.google.com/maps?q={float(gps[0]):.7f},{float(gps[1]):.7f}",
            }
        )
    return results


def _tensor_like_to_list(value: Any) -> list[Any]:
    if hasattr(value, "detach"):
        value = value.detach()
    if hasattr(value, "cpu"):
        value = value.cpu()
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, list):
        return value
    return [value]


def _build_compact_index(source: NetryxSource) -> dict[str, Any] | None:
    with _netryx_imports(source):
        ok = bool(build_compact_index(source.root))
    print("Compact index build completed." if ok else "Compact index build failed.")
    return {"success": ok, "index_dir": str(source.index_dir)}


def _create_local_index(source: NetryxSource, config: dict[str, Any]) -> dict[str, Any] | None:
    center = (
        _bounded_float(config.get("center_lat"), 0.0, minimum=-90.0, maximum=90.0),
        _bounded_float(config.get("center_lon"), 0.0, minimum=-180.0, maximum=180.0),
    )
    radius_km = _bounded_float(config.get("radius_km"), 1.0, minimum=0.1, maximum=100.0)
    grid_resolution = _bounded_int(config.get("grid_resolution"), 300, minimum=1, maximum=1000)
    crop_fov = _bounded_int(config.get("crop_fov"), 90, minimum=30, maximum=140)
    crop_size = _bounded_int(config.get("crop_size"), 256, minimum=64, maximum=1024)
    crop_step = _bounded_int(config.get("crop_step"), 90, minimum=10, maximum=360)
    print(
        "Creating local visual index around "
        f"lat={center[0]:.6f}, lon={center[1]:.6f}, radius={radius_km:g}km "
        f"(grid={grid_resolution}, headings every {crop_step} degrees)."
    )
    with _netryx_imports(source):
        from laitoxx.features.photo_geolocation.photo2geo_indexer import create_local_index

        return create_local_index(
            source.root,
            center=center,
            radius_km=radius_km,
            grid_resolution=grid_resolution,
            crop_fov=crop_fov,
            crop_size=crop_size,
            crop_step=crop_step,
            progress_callback=_emit_download_progress,
        )


def _hub_list(source: NetryxSource) -> dict[str, Any] | None:
    with _netryx_imports(source):
        from netryx_hub import NetryxHub

        indexes = NetryxHub().list_indexes()
    _print_hub_indexes(indexes)
    return {"indexes": indexes}


def _hub_search(source: NetryxSource, config: dict[str, Any]) -> dict[str, Any] | None:
    city = str(config.get("city") or "").strip() or None
    lat = _optional_float(config.get("center_lat"))
    lon = _optional_float(config.get("center_lon"))
    max_distance_km = _bounded_float(
        config.get("max_distance_km"), 100.0, minimum=1.0, maximum=5000.0
    )
    with _netryx_imports(source):
        from netryx_hub import NetryxHub

        indexes = NetryxHub().search(lat=lat, lon=lon, max_distance_km=max_distance_km, city=city)
    _print_hub_indexes(indexes)
    return {"indexes": indexes}


def _hub_download(source: NetryxSource, config: dict[str, Any]) -> dict[str, Any] | None:
    repo_id = str(config.get("repo_id") or "").strip()
    if not repo_id:
        print("Error: repo_id is required for hub_download mode.")
        return None
    output_dir = Path(str(config.get("index_dir") or source.index_dir)).expanduser()
    expected_size = _download_sizes(config).get(repo_id)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="hub_download_", dir=output_dir.parent) as temp_dir:
        manifest, _ = _download_hub_index(
            source,
            repo_id,
            Path(temp_dir),
            index=1,
            count=1,
            completed_bytes=0,
            total_bytes=expected_size,
        )
        if manifest is None:
            return None
        _emit_download_progress({"phase": "installing", "message": "Installing downloaded index"})
        _install_downloaded_index(Path(temp_dir), output_dir)
    print(f"Downloaded index: {manifest.get('name', repo_id) if manifest else repo_id}")
    return {"manifest": manifest, "index_dir": str(output_dir)}


def _hub_download_all(source: NetryxSource, config: dict[str, Any]) -> dict[str, Any] | None:
    repo_ids = list(
        dict.fromkeys(
            str(repo_id).strip() for repo_id in config.get("repo_ids", []) if str(repo_id).strip()
        )
    )
    if not repo_ids:
        print("Error: no hub indexes were selected for download.")
        return None
    output_dir = Path(str(config.get("index_dir") or source.index_dir)).expanduser()
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    expected_sizes = _download_sizes(config)
    total_bytes = (
        sum(expected_sizes[repo_id] for repo_id in repo_ids)
        if all(expected_sizes.get(repo_id) for repo_id in repo_ids)
        else None
    )
    completed_bytes = 0
    manifests = []
    with tempfile.TemporaryDirectory(prefix="hub_download_", dir=output_dir.parent) as temp_dir:
        staged_indexes = []
        for position, repo_id in enumerate(repo_ids, 1):
            stage_dir = Path(temp_dir) / str(position)
            manifest, item_bytes = _download_hub_index(
                source,
                repo_id,
                stage_dir,
                index=position,
                count=len(repo_ids),
                completed_bytes=completed_bytes,
                total_bytes=total_bytes,
            )
            if manifest is None:
                return None
            completed_bytes += item_bytes
            manifests.append(manifest)
            staged_indexes.append(stage_dir)
            print(f"Downloaded index: {manifest.get('name', repo_id) if manifest else repo_id}")
        _emit_download_progress({"phase": "installing", "message": "Combining downloaded indexes"})
        if not merge_compact_indexes(staged_indexes, output_dir):
            return None
    return {"manifests": manifests, "index_dir": str(output_dir)}


def _download_hub_index(
    source: NetryxSource,
    repo_id: str,
    output_dir: Path,
    *,
    index: int,
    count: int,
    completed_bytes: int,
    total_bytes: int | None,
) -> tuple[dict[str, Any] | None, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        bundle_path, item_bytes = _download_bundle(
            repo_id,
            output_dir,
            index=index,
            count=count,
            completed_bytes=completed_bytes,
            total_bytes=total_bytes,
        )
    except requests.HTTPError as exc:
        if exc.response is None or exc.response.status_code != 404:
            raise
        _emit_download_progress(
            {
                "phase": "fallback",
                "repo_id": repo_id,
                "index": index,
                "count": count,
                "message": "Bundle not found; downloading index files separately",
            }
        )
        with _netryx_imports(source):
            from netryx_hub import NetryxHub

            manifest = NetryxHub().download(
                repo_id,
                str(output_dir),
                progress_callback=lambda message: _emit_download_progress(
                    {
                        "phase": "fallback",
                        "repo_id": repo_id,
                        "index": index,
                        "count": count,
                        "message": message,
                    }
                ),
            )
        return manifest, int(total_bytes or 0)

    _emit_download_progress(
        {
            "phase": "extracting",
            "repo_id": repo_id,
            "index": index,
            "count": count,
            "message": "Extracting downloaded index",
        }
    )
    with _netryx_imports(source):
        from netryx_hub import extract_bundle

        manifest = extract_bundle(str(bundle_path), str(output_dir))
    return manifest, item_bytes


def _download_bundle(
    repo_id: str,
    output_dir: Path,
    *,
    index: int,
    count: int,
    completed_bytes: int,
    total_bytes: int | None,
) -> tuple[Path, int]:
    from huggingface_hub import hf_hub_url
    from huggingface_hub.utils import build_hf_headers, get_session

    bundle_path = output_dir / "index.netryx"
    url = hf_hub_url(repo_id, "index.netryx", repo_type="dataset")
    headers = build_hf_headers(
        library_name="laitoxx",
        user_agent="photo-geolocation",
    )
    started_at = time.monotonic()
    downloaded = 0
    with get_session().get(url, headers=headers, stream=True, timeout=60) as response:
        response.raise_for_status()
        response_length = _positive_int(response.headers.get("Content-Length"))
        aggregate_total = total_bytes or (response_length if count == 1 else None)
        with bundle_path.open("wb") as output:
            for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                if not chunk:
                    continue
                output.write(chunk)
                downloaded += len(chunk)
                elapsed = max(time.monotonic() - started_at, 1e-6)
                speed_bps = downloaded / elapsed
                aggregate_done = completed_bytes + downloaded
                eta_seconds = (
                    max(aggregate_total - aggregate_done, 0) / speed_bps
                    if aggregate_total and speed_bps > 0
                    else None
                )
                _emit_download_progress(
                    {
                        "phase": "downloading",
                        "repo_id": repo_id,
                        "index": index,
                        "count": count,
                        "downloaded_bytes": aggregate_done,
                        "total_bytes": aggregate_total,
                        "speed_bps": speed_bps,
                        "eta_seconds": eta_seconds,
                    }
                )
    return bundle_path, downloaded


def _install_downloaded_index(source_dir: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename in (
        "megaloc_descriptors.npy",
        "metadata.npz",
        "megaloc_pca.pkl",
        "manifest.json",
        "index_info.txt",
    ):
        source_file = source_dir / filename
        if source_file.exists():
            source_file.replace(output_dir / filename)


def _download_sizes(config: dict[str, Any]) -> dict[str, int]:
    raw_sizes = config.get("repo_sizes")
    if not isinstance(raw_sizes, dict):
        return {}
    return {
        str(repo_id): size
        for repo_id, value in raw_sizes.items()
        if (size := _positive_int(value)) is not None
    }


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _format_bytes(value: int | float) -> str:
    size = float(value or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def _emit_download_progress(event: dict[str, Any]) -> None:
    print(f"{PROGRESS_MARKER}{json.dumps(event, ensure_ascii=False)}", flush=True)


def _import_bundle(source: NetryxSource, config: dict[str, Any]) -> dict[str, Any] | None:
    bundle_path = Path(str(config.get("bundle_path") or "")).expanduser()
    if not bundle_path.is_file():
        print(f"Error: .netryx bundle not found: {bundle_path}")
        return None
    output_dir = Path(str(config.get("index_dir") or source.index_dir)).expanduser()
    with _netryx_imports(source):
        from netryx_hub import extract_bundle

        manifest = extract_bundle(str(bundle_path), str(output_dir))
    print(f"Imported bundle: {manifest.get('name', bundle_path.name)}")
    return {"manifest": manifest, "index_dir": str(output_dir)}


def _export_bundle(source: NetryxSource, config: dict[str, Any]) -> dict[str, Any] | None:
    output_path = Path(str(config.get("bundle_path") or "photo2geo_index.netryx")).expanduser()
    index_dir = Path(str(config.get("index_dir") or source.index_dir)).expanduser()
    name = str(config.get("name") or "Laitoxx Photo geolocation Index")
    center_lat = _to_float(config.get("center_lat"), 0.0)
    center_lon = _to_float(config.get("center_lon"), 0.0)
    radius_km = _bounded_float(config.get("radius_km"), 1.0, minimum=0.1, maximum=5000.0)
    with _netryx_imports(source):
        from netryx_hub import create_bundle

        bundle_path, manifest = create_bundle(
            index_dir=str(index_dir),
            output_path=str(output_path),
            name=name,
            description="Exported from Laitoxx Photo geolocation",
            center_lat=center_lat,
            center_lon=center_lon,
            radius_km=radius_km,
            tags=["laitoxx", "photo2geo", "netryx"],
            creator="laitoxx",
        )
    print(f"Exported bundle: {bundle_path}")
    return {"bundle_path": str(bundle_path), "manifest": manifest}


@contextmanager
def _netryx_imports(source: NetryxSource):
    if not source.root.is_dir():
        raise FileNotFoundError(
            f"Netryx Astra source path not found: {source.root}. "
            "Set NETRYX_ASTRA_PATH or fill Source path in the form."
        )
    previous_path = list(sys.path)
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    sys.path.insert(0, str(source.root))
    try:
        yield
    finally:
        sys.path[:] = previous_path


def _discover_module_functions(source: NetryxSource) -> dict[str, list[str]]:
    discovered: dict[str, list[str]] = {}
    for module_name in NETRYX_MODULES:
        module_path = source.module_path(module_name)
        if not module_path.exists():
            discovered[module_name] = []
            continue
        try:
            tree = ast.parse(module_path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            discovered[module_name] = []
            continue
        names = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
        discovered[module_name] = names
    return discovered


def _print_search_results(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No matching locations found in the selected index/radius.")
        return
    print(f"Found {len(results)} candidate locations:")
    print("Rank  Score    Latitude      Longitude     Heading  Panoid / Map")
    print("--------------------------------------------------------------------------")
    for index, result in enumerate(results[:25], 1):
        lat = float(result.get("lat", 0.0))
        lon = float(result.get("lon", 0.0))
        map_url = f"https://www.google.com/maps?q={lat:.7f},{lon:.7f}"
        print(
            f"{index:<5} {float(result.get('score', 0.0)):<8.4f} "
            f"{lat:<13.7f} "
            f"{lon:<13.7f} "
            f"{int(result.get('heading', 0)):<8} {result.get('panoid', '')} | {map_url}"
        )


def _print_geoclip_results(results: list[dict[str, Any]]) -> None:
    if not results:
        print("No GeoCLIP predictions returned.")
        return
    print(f"Found {len(results)} worldwide candidate location(s):")
    print("Rank  Probability  Latitude      Longitude     Map")
    print("--------------------------------------------------------------------------")
    for result in results:
        lat = float(result.get("lat", 0.0))
        lon = float(result.get("lon", 0.0))
        probability = result.get("probability")
        probability_text = "n/a" if probability is None else f"{float(probability):.6f}"
        print(
            f"{int(result.get('rank', 0)):<5} {probability_text:<12} "
            f"{lat:<13.7f} {lon:<13.7f} {result.get('map_url', '')}"
        )


def _print_hub_indexes(indexes: list[dict[str, Any]]) -> None:
    if not indexes:
        print("No Netryx indexes found.")
        return
    print(f"Found {len(indexes)} Netryx index(es):")
    for index in indexes[:50]:
        print(
            f"- {index.get('name', 'Unknown')} | "
            f"repo={index.get('repo_id', '?')} | "
            f"center={index.get('center_lat', '?')},{index.get('center_lon', '?')} | "
            f"radius={index.get('radius_km', '?')}km | "
            f"entries={index.get('num_entries', '?')}"
        )


def _read_interactive_config() -> dict[str, Any]:
    engine = input("Engine netryx/geoclip [netryx]: ").strip().lower() or "netryx"
    mode = (
        input(
            "Mode status/search/create_index/build_index/hub_list/hub_search/hub_download/import_bundle/export_bundle [status]: "
        ).strip()
        or "status"
    )
    config: dict[str, Any] = {"engine": engine, "mode": mode}
    if engine != "geoclip":
        config["source_path"] = input(
            f"Netryx source path [{DEFAULT_NETRYX_PATH}]: "
        ).strip() or str(DEFAULT_NETRYX_PATH)
    if mode == "search":
        config["image_path"] = input("Query image path: ").strip()
        if engine == "geoclip":
            config["top_k"] = input("Top K [5]: ").strip() or "5"
            config["model_device"] = input("Device auto/cpu/cuda [auto]: ").strip() or "auto"
            config["precision"] = (
                input("Precision auto/float32/bfloat16/float16 [auto]: ").strip() or "auto"
            )
        else:
            config["center_lat"] = input("Center latitude: ").strip()
            config["center_lon"] = input("Center longitude: ").strip()
            config["radius_km"] = input("Radius km [1]: ").strip() or "1"
            config["top_k"] = input("Top K [25]: ").strip() or "25"
    elif mode == "create_index":
        config["center_lat"] = input("Center latitude: ").strip()
        config["center_lon"] = input("Center longitude: ").strip()
        config["radius_km"] = input("Radius km [1]: ").strip() or "1"
        config["grid_resolution"] = input("Grid resolution [300]: ").strip() or "300"
    return config


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return _to_float(value, 0.0)


def _bounded_float(value: Any, default: float, *, minimum: float, maximum: float) -> float:
    parsed = _to_float(value, default)
    return max(minimum, min(parsed, maximum))


def _bounded_int(value: Any, default: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def main(argv: list[str] | None = None) -> int:
    """Run Photo geolocation as an isolated worker process for the Textual UI."""
    parser = argparse.ArgumentParser(description="Laitoxx Photo geolocation worker")
    parser.add_argument("--config-json", default="", help="JSON encoded Photo geolocation config")
    parser.add_argument(
        "--emit-result-json",
        action="store_true",
        help="Emit a machine-readable result line for the TUI parent process",
    )
    args = parser.parse_args(argv)

    config = None
    if args.config_json:
        try:
            config = json.loads(args.config_json)
        except json.JSONDecodeError as exc:
            print(f"Error: invalid Photo geolocation config JSON: {exc}")
            return 2

    try:
        result = photo2geo_tool(config)
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    if args.emit_result_json and result is not None:
        print(f"{RESULT_MARKER}{json.dumps(result, ensure_ascii=False, default=str)}")
    return 0 if result is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
