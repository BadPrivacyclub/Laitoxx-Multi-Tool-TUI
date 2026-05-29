from __future__ import annotations

import hashlib
import os
import pickle
import shutil
import time
from pathlib import Path
from typing import Any

INDEX_TARGET_DIM = 1024
MAX_PCA_SAMPLES = 100_000
SEARCH_CHUNK_SIZE = 100_000

_COMPACT_CACHE: dict[Path, tuple[Any, dict[str, Any]]] = {}


def get_index_dir(source_root: Path) -> Path:
    return source_root / "netryx_data" / "index"


def get_parts_dir(source_root: Path) -> Path:
    return source_root / "netryx_data" / "megaloc_parts"


def get_embeddings_csv(source_root: Path) -> Path:
    return source_root / "netryx_data" / "embeddings_index.csv"


def build_compact_index(source_root: Path) -> bool:
    """Build a compact Netryx index without importing the original Tkinter GUI."""
    import numpy as np

    index_dir = get_index_dir(source_root)
    parts_dir = get_parts_dir(source_root)
    embeddings_csv = get_embeddings_csv(source_root)
    index_dir.mkdir(parents=True, exist_ok=True)

    part_files = sorted(set(parts_dir.glob("megaloc_part_*.npz")))
    if not part_files:
        print("[INDEX] ERROR: No MegaLoc part files found.")
        return False

    print(f"[INDEX] Found {len(part_files)} part files.")
    total, raw_dim = _count_entries(part_files)
    print(f"[INDEX] Total entries: {total}, raw descriptor dim: {raw_dim}")

    needs_pca = raw_dim > INDEX_TARGET_DIM
    final_dim = min(INDEX_TARGET_DIM, total) if needs_pca else raw_dim
    pca = _fit_pca(part_files, index_dir, final_dim) if needs_pca else None
    if not needs_pca:
        print(f"[INDEX] Descriptors already {raw_dim}-dim, no PCA needed.")

    descriptors, paths, embedded_lats, embedded_lons = _merge_descriptor_parts(
        part_files,
        total=total,
        final_dim=final_dim,
        pca=pca,
    )
    total = len(paths)
    csv_locations, csv_full_locations = _read_coordinate_csv(embeddings_csv)
    metadata = _build_metadata(
        paths, embedded_lats, embedded_lons, csv_locations, csv_full_locations
    )

    valid_idx = np.where(metadata["valid_mask"])[0]
    print(f"[INDEX] Keeping {len(valid_idx)} entries with valid coordinates.")
    if len(valid_idx) == 0:
        print("[INDEX] ERROR: No indexed entries have coordinates.")
        return False

    descs_valid = descriptors[valid_idx].copy()
    del descriptors
    _normalize_in_place(descs_valid)

    descs_path = index_dir / "megaloc_descriptors.npy"
    meta_path = index_dir / "metadata.npz"
    np.save(descs_path, descs_valid)
    np.savez_compressed(
        meta_path,
        lats=metadata["lats"][valid_idx],
        lons=metadata["lons"][valid_idx],
        headings=metadata["headings"][valid_idx],
        panoids=np.array([metadata["panoids"][i] for i in valid_idx], dtype=object),
        paths=np.array([paths[i] for i in valid_idx], dtype=object),
    )

    _write_index_info(index_dir, descs_path, meta_path, len(valid_idx), final_dim, raw_dim)
    _COMPACT_CACHE.pop(index_dir.resolve(), None)
    return True


def load_compact_index(index_dir: Path) -> tuple[Any | None, dict[str, Any] | None]:
    """Load Netryx compact index files from disk."""
    import numpy as np

    index_dir = index_dir.resolve()
    if index_dir in _COMPACT_CACHE:
        return _COMPACT_CACHE[index_dir]

    descs_path = index_dir / "megaloc_descriptors.npy"
    meta_path = index_dir / "metadata.npz"
    if not descs_path.exists() or not meta_path.exists():
        print(f"[INDEX] ERROR: Compact index not found in {index_dir}.")
        return None, None

    print("[INDEX] Loading compact index (memory-mapped)...")
    started_at = time.time()
    descriptors = np.load(descs_path, mmap_mode="r")
    meta = np.load(meta_path, allow_pickle=True)
    metadata = {
        "lats": meta["lats"].copy(),
        "lons": meta["lons"].copy(),
        "headings": meta["headings"].copy(),
        "panoids": meta["panoids"],
        "paths": meta["paths"],
    }
    print(
        f"[INDEX] Loaded {len(descriptors)} entries "
        f"({descriptors.shape[1]}-dim) in {time.time() - started_at:.1f}s."
    )
    _COMPACT_CACHE[index_dir] = (descriptors, metadata)
    return descriptors, metadata


def merge_compact_indexes(index_dirs: list[Path], output_dir: Path) -> bool:
    """Merge downloaded compact indexes without overwriting earlier downloads."""
    import numpy as np

    descriptor_chunks = []
    metadata_chunks: dict[str, list[Any]] = {
        "lats": [],
        "lons": [],
        "headings": [],
        "panoids": [],
        "paths": [],
    }
    pca_paths = []
    descriptor_dim: int | None = None
    for index_dir in index_dirs:
        descriptors_path = index_dir / "megaloc_descriptors.npy"
        metadata_path = index_dir / "metadata.npz"
        if not descriptors_path.exists() or not metadata_path.exists():
            print(f"[INDEX] ERROR: downloaded index files missing in {index_dir}.")
            return False

        descriptors = np.load(descriptors_path)
        metadata = np.load(metadata_path, allow_pickle=True)
        if descriptor_dim is None:
            descriptor_dim = int(descriptors.shape[1])
        elif descriptors.shape[1] != descriptor_dim:
            print("[INDEX] ERROR: community indexes use incompatible descriptor dimensions.")
            return False
        if len(descriptors) != len(metadata["lats"]):
            print(f"[INDEX] ERROR: invalid metadata length in {index_dir}.")
            return False

        descriptor_chunks.append(np.asarray(descriptors, dtype=np.float32))
        for name in metadata_chunks:
            metadata_chunks[name].append(metadata[name])
        pca_path = index_dir / "megaloc_pca.pkl"
        if pca_path.exists():
            pca_paths.append(pca_path)

    if not descriptor_chunks:
        print("[INDEX] ERROR: no community indexes were downloaded.")
        return False
    if pca_paths and len(pca_paths) != len(descriptor_chunks):
        print("[INDEX] ERROR: cannot merge indexes when only some contain a PCA model.")
        return False
    if pca_paths:
        first_hash = hashlib.sha256(pca_paths[0].read_bytes()).digest()
        if any(hashlib.sha256(path.read_bytes()).digest() != first_hash for path in pca_paths[1:]):
            print("[INDEX] ERROR: cannot merge indexes built with different PCA models.")
            return False

    output_dir.mkdir(parents=True, exist_ok=True)
    merged_descriptors = np.vstack(descriptor_chunks)
    np.save(output_dir / "megaloc_descriptors.npy", merged_descriptors)
    np.savez_compressed(
        output_dir / "metadata.npz",
        **{name: np.concatenate(chunks) for name, chunks in metadata_chunks.items()},
    )
    output_pca = output_dir / "megaloc_pca.pkl"
    if pca_paths:
        shutil.copy2(pca_paths[0], output_pca)
    elif output_pca.exists():
        output_pca.unlink()
    _COMPACT_CACHE.pop(output_dir.resolve(), None)
    print(f"[INDEX] Installed combined community index: {len(merged_descriptors)} entries.")
    return True


def search_compact_index(
    query_desc: Any,
    center: tuple[float, float],
    radius_km: float,
    *,
    index_dir: Path,
    top_k: int = 500,
) -> list[dict[str, Any]]:
    """Search a compact Netryx index by descriptor and geographic radius."""
    import numpy as np

    descriptors, metadata = load_compact_index(index_dir)
    if descriptors is None or metadata is None:
        return []

    started_at = time.time()
    lat1 = np.radians(center[0])
    lon1 = np.radians(center[1])
    lat2 = np.radians(metadata["lats"])
    lon2 = np.radians(metadata["lons"])
    distances = _haversine_radians(lat1, lon1, lat2, lon2)
    radius_indices = np.where(distances <= radius_km)[0]
    print(
        f"[INDEX] Radius filter: {len(radius_indices)}/{len(descriptors)} "
        f"in {radius_km:g}km ({time.time() - started_at:.2f}s)."
    )
    if len(radius_indices) == 0:
        return []

    query_norm = query_desc / (np.linalg.norm(query_desc) + 1e-8)
    query_norm = query_norm.astype(np.float32)
    top_scores = np.full(max(1, top_k * 2), -np.inf, dtype=np.float32)
    top_indices = np.zeros(max(1, top_k * 2), dtype=np.int64)

    for chunk_start in range(0, len(radius_indices), SEARCH_CHUNK_SIZE):
        chunk_end = min(chunk_start + SEARCH_CHUNK_SIZE, len(radius_indices))
        chunk_idx = radius_indices[chunk_start:chunk_end]
        chunk_descs = np.array(descriptors[chunk_idx], dtype=np.float32)
        chunk_sims = chunk_descs @ query_norm
        combined_scores = np.concatenate([top_scores, chunk_sims])
        combined_indices = np.concatenate([top_indices, chunk_idx])
        keep = min(len(top_scores), len(combined_scores))
        best = np.argsort(combined_scores)[::-1][:keep]
        top_scores = combined_scores[best]
        top_indices = combined_indices[best]

    results = _deduplicate_panoids(top_indices, top_scores, metadata, top_k)
    best = f"{results[0]['score']:.3f}" if results else "n/a"
    print(f"[INDEX] Search: top-{len(results)} unique panoids (best: {best}).")
    return results


def _count_entries(part_files: list[Path]) -> tuple[int, int]:
    import numpy as np

    total = 0
    raw_dim = 0
    for part_file in part_files:
        data = np.load(part_file, allow_pickle=True)
        total += len(data["paths"])
        if raw_dim == 0:
            raw_dim = int(data["descriptors"].shape[1])
        del data
    return total, raw_dim


def _fit_pca(part_files: list[Path], index_dir: Path, final_dim: int) -> Any:
    import numpy as np
    from sklearn.decomposition import PCA

    print(f"[INDEX] Will apply PCA to {final_dim} dimensions.")
    samples = []
    sample_count = 0
    for part_file in part_files:
        if sample_count >= MAX_PCA_SAMPLES:
            break
        data = np.load(part_file, allow_pickle=True)
        descriptors = data["descriptors"]
        remaining = MAX_PCA_SAMPLES - sample_count
        samples.append(descriptors[:remaining])
        sample_count += len(descriptors[:remaining])
        del data

    matrix = np.vstack(samples)
    print(f"[INDEX] Fitting PCA on {matrix.shape[0]} samples...")
    pca = PCA(n_components=final_dim, whiten=True)
    pca.fit(matrix)
    explained = pca.explained_variance_ratio_.sum()
    print(f"[INDEX] PCA fitted. Explained variance: {explained * 100:.1f}%.")

    pca_path = index_dir / "megaloc_pca.pkl"
    with pca_path.open("wb") as file:
        pickle.dump(pca, file)
    print(f"[INDEX] Saved PCA model to {pca_path}.")
    return pca


def _merge_descriptor_parts(
    part_files: list[Path],
    *,
    total: int,
    final_dim: int,
    pca: Any | None,
) -> tuple[Any, list[str], list[float], list[float]]:
    import numpy as np

    descriptors = np.zeros((total, final_dim), dtype=np.float32)
    paths: list[str] = []
    embedded_lats: list[float] = []
    embedded_lons: list[float] = []
    row = 0
    started_at = time.time()

    for index, part_file in enumerate(part_files, 1):
        data = np.load(part_file, allow_pickle=True)
        chunk = data["descriptors"]
        count = len(data["paths"])
        if pca is not None and chunk.shape[1] > final_dim:
            chunk = pca.transform(chunk).astype(np.float32)
            _normalize_in_place(chunk)
        elif chunk.shape[1] != final_dim:
            print(f"[INDEX] WARNING: skipping {part_file}, dim {chunk.shape[1]} != {final_dim}.")
            del data
            continue

        descriptors[row : row + count] = chunk
        paths.extend(data["paths"].tolist())
        embedded_lats.extend(data["lats"].tolist() if "lats" in data else [0.0] * count)
        embedded_lons.extend(data["lons"].tolist() if "lons" in data else [0.0] * count)
        row += count
        del data, chunk

        if index % 100 == 0:
            print(
                f"[INDEX] Loaded {index}/{len(part_files)} parts in {time.time() - started_at:.0f}s."
            )

    if row < total:
        descriptors = descriptors[:row]
    return descriptors, paths, embedded_lats, embedded_lons


def _read_coordinate_csv(
    csv_path: Path,
) -> tuple[dict[str, tuple[float, float]], dict[str, tuple[float, float]]]:
    csv_locations: dict[str, tuple[float, float]] = {}
    csv_full_locations: dict[str, tuple[float, float]] = {}
    if not csv_path.exists():
        return csv_locations, csv_full_locations

    with csv_path.open(encoding="utf-8", errors="ignore") as file:
        for line in file:
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue
            try:
                lat, lon = float(parts[1]), float(parts[2])
            except ValueError:
                continue
            csv_full_locations[parts[0]] = (lat, lon)
            csv_locations[os.path.basename(parts[0])] = (lat, lon)
    print(f"[INDEX] CSV has {len(csv_locations)} location entries.")
    return csv_locations, csv_full_locations


def _build_metadata(
    paths: list[str],
    embedded_lats: list[float],
    embedded_lons: list[float],
    csv_locations: dict[str, tuple[float, float]],
    csv_full_locations: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    import numpy as np

    lats = np.zeros(len(paths), dtype=np.float32)
    lons = np.zeros(len(paths), dtype=np.float32)
    headings = np.zeros(len(paths), dtype=np.int16)
    panoids: list[str] = []
    valid_mask = np.zeros(len(paths), dtype=bool)
    matched = 0

    for index, path in enumerate(paths):
        filename = os.path.basename(path)
        panoid, heading = _parse_emb_path(filename)
        panoids.append(panoid or "")
        headings[index] = heading or 0

        emb_lat = embedded_lats[index]
        emb_lon = embedded_lons[index]
        if emb_lat != 0 or emb_lon != 0:
            lats[index], lons[index] = emb_lat, emb_lon
            valid_mask[index] = True
            matched += 1
            continue

        location = csv_full_locations.get(path) or csv_locations.get(filename)
        if location:
            lats[index], lons[index] = location
            valid_mask[index] = True
            matched += 1

    print(f"[INDEX] Matched {matched}/{len(paths)} paths to coordinates.")
    return {
        "lats": lats,
        "lons": lons,
        "headings": headings,
        "panoids": panoids,
        "valid_mask": valid_mask,
    }


def _parse_emb_path(path: str) -> tuple[str | None, int | None]:
    name = os.path.basename(path).replace(".npz", "")
    parts = name.rsplit("_", 1)
    if len(parts) != 2:
        return None, None
    try:
        return parts[0], int(parts[1])
    except ValueError:
        return None, None


def _normalize_in_place(descriptors: Any) -> None:
    import numpy as np

    norms = np.linalg.norm(descriptors, axis=1, keepdims=True)
    norms[norms == 0] = 1
    descriptors /= norms


def _haversine_radians(lat1: Any, lon1: Any, lat2: Any, lon2: Any) -> Any:
    import numpy as np

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6371 * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def _deduplicate_panoids(
    top_indices: Any,
    top_scores: Any,
    metadata: dict[str, Any],
    top_k: int,
) -> list[dict[str, Any]]:
    import numpy as np

    seen: dict[str, dict[str, Any]] = {}
    for global_index, score in zip(top_indices, top_scores, strict=False):
        if score == -np.inf:
            break
        panoid = str(metadata["panoids"][global_index])
        if panoid not in seen or score > seen[panoid]["score"]:
            seen[panoid] = {
                "panoid": panoid,
                "heading": int(metadata["headings"][global_index]),
                "lat": float(metadata["lats"][global_index]),
                "lon": float(metadata["lons"][global_index]),
                "score": float(score),
                "path": str(metadata["paths"][global_index]),
            }
    return sorted(seen.values(), key=lambda item: item["score"], reverse=True)[:top_k]


def _write_index_info(
    index_dir: Path,
    descs_path: Path,
    meta_path: Path,
    entries: int,
    final_dim: int,
    raw_dim: int,
) -> None:
    total_mb = (descs_path.stat().st_size + meta_path.stat().st_size) / 1024 / 1024
    info_path = index_dir / "index_info.txt"
    info_path.write_text(
        "\n".join(
            [
                "Compact Index Info",
                f"Built: {time.strftime('%Y-%m-%d %H:%M:%S')}",
                f"Entries: {entries}",
                f"Descriptor dim: {final_dim}",
                f"Raw dim (pre-PCA): {raw_dim}",
                f"Total: {total_mb:.1f} MB",
            ]
        ),
        encoding="utf-8",
    )
    print(f"[INDEX] Saved compact index to {index_dir} ({entries} entries, {total_mb:.1f} MB).")
