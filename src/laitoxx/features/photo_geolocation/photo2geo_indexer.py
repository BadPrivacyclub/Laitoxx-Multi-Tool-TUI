from __future__ import annotations

import asyncio
import io
import itertools
import math
import os
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from laitoxx.features.photo_geolocation.photo2geo_backend import build_compact_index, get_parts_dir

ProgressCallback = Callable[[dict[str, Any]], None]


def create_local_index(
    source_root: Path,
    *,
    center: tuple[float, float],
    radius_km: float,
    grid_resolution: int,
    crop_fov: int,
    crop_size: int,
    crop_step: int,
    progress_callback: ProgressCallback,
) -> dict[str, Any] | None:
    from megaloc_utils import batch_extract_megaloc

    points = grid_points(center, radius_km, grid_resolution)
    progress_callback(
        {
            "phase": "indexing",
            "stage": "scan",
            "message": f"Scanning {len(points)} grid points for Street View panoramas",
            "progress": 0,
            "total": len(points),
            "unit": "grid points",
        }
    )
    scan_started = time.monotonic()
    panoids = asyncio.run(
        _get_panoids(
            points,
            lambda done, total: progress_callback(
                _progress_event(
                    "scan",
                    "Scanning Street View coverage",
                    done,
                    total,
                    scan_started,
                    "grid points",
                )
            ),
        )
    )
    if not panoids:
        print("Error: no Street View panoramas found in the selected area.")
        return None

    headings = list(range(0, 360, crop_step))
    parts_dir = get_parts_dir(source_root)
    parts_dir.mkdir(parents=True, exist_ok=True)
    existing = _existing_paths(parts_dir)
    process_started = time.monotonic()
    extracted = 0
    for position, panorama in enumerate(panoids, 1):
        missing_headings = [
            heading for heading in headings if f"{panorama['panoid']}_{heading}.npz" not in existing
        ]
        if missing_headings:
            crops = asyncio.run(
                _download_crops(
                    str(panorama["panoid"]),
                    missing_headings,
                    crop_fov=crop_fov,
                    crop_size=crop_size,
                )
            )
            if crops:
                descriptors = batch_extract_megaloc(
                    crops,
                    batch_size=min(32, len(crops)),
                    apply_pca_reduction=False,
                )
                paths = [
                    f"{panorama['panoid']}_{heading}.npz"
                    for heading in missing_headings[: len(descriptors)]
                ]
                _save_part(parts_dir, descriptors, paths, panorama)
                extracted += len(paths)
        progress_callback(
            _progress_event(
                "panoramas",
                "Downloading panoramas and extracting MegaLoc descriptors",
                position,
                len(panoids),
                process_started,
                "panoramas",
            )
        )

    progress_callback(
        {
            "phase": "indexing",
            "stage": "building",
            "message": "Fitting PCA and building compact search index; cancellation is unavailable",
        }
    )
    if not build_compact_index(source_root):
        return None
    progress_callback(
        {
            "phase": "indexing",
            "stage": "complete",
            "message": f"Index ready: {extracted} new visual descriptors added",
        }
    )
    return {
        "center": center,
        "radius_km": radius_km,
        "panoids": len(panoids),
        "new_entries": extracted,
        "index_dir": str(source_root / "netryx_data" / "index"),
    }


def grid_points(
    center: tuple[float, float], radius_km: float, resolution: int
) -> list[tuple[float, float]]:
    lat, lon = center
    lat_delta = math.degrees(radius_km / 6371.0)
    longitude_scale = max(abs(math.cos(math.radians(lat))), 1e-6)
    lon_delta = min(180.0, lat_delta / longitude_scale)
    candidates = (
        (
            lat - lat_delta + x * (2 * lat_delta) / resolution,
            _normalize_longitude(lon - lon_delta + y * (2 * lon_delta) / resolution),
        )
        for x, y in itertools.product(range(resolution + 1), repeat=2)
    )
    return [point for point in candidates if _haversine(point, center) <= radius_km]


def _progress_event(
    stage: str,
    message: str,
    progress: int,
    total: int,
    started_at: float,
    unit: str,
) -> dict[str, Any]:
    elapsed = max(time.monotonic() - started_at, 1e-6)
    speed = progress / elapsed
    eta = (total - progress) / speed if progress and speed > 0 else None
    return {
        "phase": "indexing",
        "stage": stage,
        "message": message,
        "progress": progress,
        "total": total,
        "unit": unit,
        "speed_per_second": speed,
        "eta_seconds": eta,
    }


async def _get_panoids(
    points: list[tuple[float, float]],
    progress_callback: Callable[[int, int], None],
) -> list[dict[str, Any]]:
    import aiohttp

    async def fetch(session: aiohttp.ClientSession, lat: float, lon: float) -> list[dict[str, Any]]:
        url = (
            "https://maps.googleapis.com/maps/api/js/GeoPhotoService.SingleImageSearch?"
            f"pb=!1m5!1sapiv3!5sUS!11m2!1m1!1b0!2m4!1m2!3d{lat}!4d{lon}!2d50!"
            "3m10!2m2!1sen!2sGB!9m1!1e2!11m4!1m3!1e2!2b1!3e2&callback=_xdc_._v2mub5"
        )
        for _ in range(3):
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 429:
                        await asyncio.sleep(1)
                        continue
                    if response.status != 200:
                        return []
                    return _parse_panoids(await response.text())
            except (aiohttp.ClientError, TimeoutError):
                await asyncio.sleep(0.2)
        return []

    connector = aiohttp.TCPConnector(limit=16)
    results = []
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch(session, lat, lon) for lat, lon in points]
        for completed, task in enumerate(asyncio.as_completed(tasks), 1):
            results.extend(await task)
            progress_callback(completed, len(points))
    unique = {}
    for panorama in results:
        if panorama.get("lat") is not None and panorama.get("lon") is not None:
            unique[str(panorama["panoid"])] = panorama
    print(f"[INDEX] Found {len(unique)} unique Street View panoramas.")
    return list(unique.values())


async def _download_crops(
    panoid: str,
    headings: list[int],
    *,
    crop_fov: int,
    crop_size: int,
) -> list[Any]:
    import aiohttp
    import numpy as np
    from PIL import Image

    async def fetch(
        session: aiohttp.ClientSession, x: int, y: int
    ) -> tuple[int, int, bytes | None]:
        url = f"https://cbk0.google.com/cbk?output=tile&panoid={panoid}&zoom=2&x={x}&y={y}"
        try:
            async with session.get(url, timeout=20) as response:
                return x, y, await response.read() if response.status == 200 else None
        except (aiohttp.ClientError, TimeoutError):
            return x, y, None

    connector = aiohttp.TCPConnector(limit=8)
    tiles = []
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [fetch(session, x, y) for x, y in itertools.product(range(4), range(2))]
        tiles = await asyncio.gather(*tasks)
    canvas = np.zeros((1024, 2048, 3), dtype=np.uint8)
    for x, y, data in tiles:
        if not data:
            continue
        with Image.open(io.BytesIO(data)).convert("RGB") as tile:
            tile_array = np.asarray(tile)
            height, width = tile_array.shape[:2]
            canvas[y * 512 : y * 512 + height, x * 512 : x * 512 + width] = tile_array
    panorama = Image.fromarray(canvas)
    return [_perspective_crop(panorama, heading, crop_fov, crop_size) for heading in headings]


def _perspective_crop(panorama: Any, heading: int, fov: int, size: int) -> Any:
    import numpy as np
    import torch
    from PIL import Image

    pano = torch.from_numpy(np.asarray(panorama).copy()).float().permute(2, 0, 1).unsqueeze(0) / 255
    coordinates = torch.linspace(-1, 1, size)
    yy, xx = torch.meshgrid(coordinates, coordinates, indexing="ij")
    scale = math.tan(math.radians(fov) / 2)
    x = xx * scale
    y = -yy * scale
    z = torch.ones_like(x)
    norm = torch.sqrt(x * x + y * y + z * z)
    x, y, z = x / norm, y / norm, z / norm
    yaw = math.radians(heading)
    rotated_x = x * math.cos(yaw) + z * math.sin(yaw)
    rotated_z = -x * math.sin(yaw) + z * math.cos(yaw)
    lon = torch.atan2(rotated_x, rotated_z) / math.pi
    lat = -torch.asin(y.clamp(-1 + 1e-7, 1 - 1e-7)) / (math.pi / 2)
    grid = torch.stack((lon, lat), dim=-1).unsqueeze(0)
    crop = torch.nn.functional.grid_sample(pano, grid, mode="bilinear", align_corners=True)
    array = crop.squeeze(0).permute(1, 2, 0).mul(255).byte().numpy()
    return Image.fromarray(array)


def _save_part(
    parts_dir: Path, descriptors: Any, paths: list[str], panorama: dict[str, Any]
) -> None:
    import numpy as np

    part_path = parts_dir / f"megaloc_part_{time.time_ns()}.npz"
    np.savez_compressed(
        part_path,
        descriptors=descriptors,
        paths=np.array(paths, dtype=object),
        lats=np.full(len(paths), float(panorama["lat"]), dtype=np.float32),
        lons=np.full(len(paths), float(panorama["lon"]), dtype=np.float32),
    )


def _existing_paths(parts_dir: Path) -> set[str]:
    import numpy as np

    paths = set()
    for part in parts_dir.glob("megaloc_part_*.npz"):
        with np.load(part, allow_pickle=True) as data:
            paths.update(os.path.basename(str(path)) for path in data["paths"])
    return paths


def _parse_panoids(text: str) -> list[dict[str, Any]]:
    panoramas = []
    for panoid in re.findall(r'"([A-Za-z0-9_-]{22})"', text):
        location = re.findall(
            r'"' + re.escape(panoid) + r'".+?\[null,null,(-?\d+\.\d+),(-?\d+\.\d+)',
            text,
        )
        if location:
            lat, lon = map(float, location[0])
            panoramas.append({"panoid": panoid, "lat": lat, "lon": lon})
    return panoramas


def _haversine(left: tuple[float, float], right: tuple[float, float]) -> float:
    radius = 6371.0
    lat1, lon1 = map(math.radians, left)
    lat2, lon2 = map(math.radians, right)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def _normalize_longitude(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0
