"""List unclassified seeded scene resources inside the active planet block."""

from __future__ import annotations

import ctypes
from pathlib import Path
import runpy

import nmspy.data.types as nms


PROJECT_ROOT = Path(__file__).parents[1]


def main() -> dict[str, object]:
    known = runpy.run_path(PROJECT_ROOT / "src" / "planet_object_types.py")
    known_hashes = known["FLORA_SCENE_HASHES"] | known["MINERAL_SCENE_HASHES"]
    catalog = runpy.run_path(
        PROJECT_ROOT / "analysis" / "runtime_stage9_catalog.py"
    )["main"]()
    selected = catalog["selected_cluster"]
    if not selected:
        raise RuntimeError("selected_cluster_empty")
    first_index = selected[0][0]
    last_index = selected[-1][0]
    resources = nms.engine_modules.mgpResourceManager.contents.mResources
    entries: list[tuple[int, int, int, str]] = []
    for index in range(first_index, last_index + 1):
        pointer = resources[index]
        if not pointer:
            continue
        resource = pointer.contents
        name = str(resource.msName).replace("\\", "/").upper()
        if not name.endswith(".SCENE.MBIN"):
            continue
        scene_hash = 0x1505
        for byte in name.encode("ascii"):
            scene_hash = (scene_hash * 0x21 + byte) & 0xFFFFFFFFFFFFFFFF
        if scene_hash in known_hashes:
            continue
        address = ctypes.addressof(resource)
        use_seed = ctypes.c_ubyte.from_address(address + 0x1A8).value
        if use_seed != 1:
            continue
        ref_count = ctypes.c_uint32.from_address(address + 0x134).value
        seed = ctypes.c_uint64.from_address(address + 0x1A0).value
        entries.append((index, ref_count, seed, name))
    return {
        "range": (first_index, last_index),
        "count": len(entries),
        "entries": entries,
    }


if __name__ == "__main__":
    main()
