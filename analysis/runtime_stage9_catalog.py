"""Read-only runtime probe for the current planet's loaded object resources."""

from __future__ import annotations

import ctypes
from pathlib import Path
import runpy
import time

import nmspy.data.types as nms


PROJECT_ROOT = Path(__file__).parents[1]
_GENERATED_TYPES = runpy.run_path(PROJECT_ROOT / "src" / "planet_object_types.py")
FLORA_SCENE_HASHES = _GENERATED_TYPES["FLORA_SCENE_HASHES"]
MINERAL_SCENE_HASHES = _GENERATED_TYPES["MINERAL_SCENE_HASHES"]
SCENE_HASH_TYPES = {
    **{scene_hash: 4 for scene_hash in FLORA_SCENE_HASHES},
    **{scene_hash: 5 for scene_hash in MINERAL_SCENE_HASHES},
}
UINT64_MASK = 0xFFFFFFFFFFFFFFFF

REFERENCE_KEYS = {
    0x84E96F1DCE7194F0,
    0xEE33490FC577154E,
    0xA972F26B9D890212,
    0xA449C830B97055A2,
    0xA55033F6731C6015,
    0x543BF5C6249CA2E1,
}

def _djb2_64(value: str) -> int:
    result = 0x1505
    for byte in value.encode("ascii"):
        result = (result * 0x21 + byte) & UINT64_MASK
    return result


def main() -> dict[str, object]:
    started = time.perf_counter()
    resources = nms.engine_modules.mgpResourceManager.contents.mResources
    matches: list[tuple[int, int, int, int, int, str]] = []
    for index, resource_pointer in enumerate(resources):
        if not resource_pointer:
            continue
        resource = resource_pointer.contents
        name = str(resource.msName).upper()
        # Exact .SCENE.MBIN names exclude dependent material/texture resources.
        # NMS.py's enum wrapper does not expose a stable int conversion here.
        if not name.endswith(".SCENE.MBIN"):
            continue
        scene_hash = _djb2_64(name)
        discovery_type = SCENE_HASH_TYPES.get(scene_hash)
        if discovery_type is None:
            continue
        address = ctypes.addressof(resource)
        seed = ctypes.c_uint64.from_address(address + 0x1A0).value
        use_seed = ctypes.c_ubyte.from_address(address + 0x1A8).value
        ref_count = ctypes.c_uint32.from_address(address + 0x134).value
        matches.append((index, seed, use_seed, ref_count, discovery_type, name))

    reference_matches = [match for match in matches if match[1] in REFERENCE_KEYS]
    active_matches = [match for match in matches if match[2] == 1 and match[3] > 1]
    clusters: list[list[tuple[int, int, int, int, int, str]]] = []
    for match in matches:
        if not clusters or match[0] - clusters[-1][-1][0] > 256:
            clusters.append([])
        clusters[-1].append(match)
    selected_cluster = max(
        clusters,
        key=lambda cluster: (
            sum(match[3] > 1 for match in cluster),
            sum(match[3] for match in cluster),
        ),
        default=[],
    )
    buckets: dict[int, tuple[int, set[int]]] = {}
    for index, seed, _use_seed, _ref_count, _discovery_type, _name in matches:
        bucket = index // 1000
        count, seeds = buckets.get(bucket, (0, set()))
        seeds.add(seed)
        buckets[bucket] = (count + 1, seeds)
    result = {
        "path_count": len(SCENE_HASH_TYPES),
        "resource_count": len(resources),
        "match_count": len(matches),
        "matches": matches,
        "active_matches": active_matches,
        "clusters": [
            (cluster[0][0], cluster[-1][0], len(cluster), sum(m[3] > 1 for m in cluster))
            for cluster in clusters
        ],
        "selected_cluster": selected_cluster,
        "buckets": {
            bucket: (count, len(seeds))
            for bucket, (count, seeds) in buckets.items()
        },
        "reference_matches": reference_matches,
        "elapsed_seconds": time.perf_counter() - started,
    }
    return result


if __name__ == "__main__":
    main()
