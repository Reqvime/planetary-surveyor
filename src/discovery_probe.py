from __future__ import annotations

import ctypes
import logging
import math
import re
import struct
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from pymhf import Mod
from pymhf.core.hooking import on_key_release

import nmspy.data.types as nms

try:
    from .planet_object_types import FLORA_SCENE_HASHES, MINERAL_SCENE_HASHES
    from .scanner_settings import (
        INITIAL_SETTINGS,
        ScannerSettings,
        load_settings,
        settings_path,
    )
except ImportError:
    from planet_object_types import FLORA_SCENE_HASHES, MINERAL_SCENE_HASHES
    from scanner_settings import INITIAL_SETTINGS, ScannerSettings, load_settings, settings_path

OWNER = "NMSDiscoveryLab stage-9 full planet discovery catalogue submit probe"
logger = logging.getLogger("DiscoveryProbe")

_GAME_FUNCTION_SIGNATURES = {
    "SubmitDiscoveryData": (
        "4C 89 4C 24 ? 44 89 44 24 ? 48 89 4C 24 ? 55 53 41 55 41 56 "
        "48 8D AC 24 ? ? ? ? 48 81 EC ? ? ? ? 48 8B D9 4C 8B F2 8B 4A ? "
        "E8 ? ? ? ? 84 C0 75 ?"
    ),
    "PostSubmitDiscovery": (
        "48 89 5C 24 ? 48 89 74 24 ? 48 89 7C 24 ? 55 41 54 41 55 41 56 41 57 "
        "48 8D AC 24 C0 C1 FF FF B8 40 3F 00 00 E8 ? ? ? ? 48 2B E0 "
        "48 8B 1D ? ? ? ? 45 33 F6"
    ),
    "IsDiscoveryKnown": (
        "48 83 EC 28 48 8B 0D ? ? ? ? 48 81 C1 ? ? ? ? E8 ? ? ? ? "
        "48 85 C0 74 ? F6 80 ? ? ? ? ? 75 ? B0 01"
    ),
}
_DETOUR_PREFIX = ("E9", "?", "?", "?", "?")
_IS_DISCOVERY_KNOWN_APPLICATION_LOAD_OFFSET = 4

_SCENE_NODE_STORED_HANDLE_OFFSET = 0x08
_SCENE_NODE_STATUS_LIVE = 2
_SCENE_NODE_STRIDE = 0x40
_SCENE_NODE_POSITION_OFFSET = 0x30

@dataclass(frozen=True)
class _GameLayout:
    profile: str
    current_planet_address_offset: int
    discovery_manager_offset: int
    discovery_lookup_context_offset: int
    post_submit_context_offset: int
    solar_system_pointer_offset: int


_GAME_LAYOUTS = (
    _GameLayout(
        "179105-179292",
        0x57A160,
        0x2CE840,
        0x849020,
        0x307848,
        0x71AF70,
    ),
    _GameLayout(
        "178938-178994",
        0x57A150,
        0x2CE840,
        0x849000,
        0x307848,
        0x71AF60,
    ),
)

_SOLAR_PLANET_COUNT_OFFSET = 0x2544
_SOLAR_PLANETS_OFFSET = 0x2E30
_PLANET_STRIDE = 0xD9170
_PLANET_DISCOVERY_DATA_OFFSET = 0x08
_PLANET_DATA_OFFSET = 0x60
_PLANET_CREATURE_ROLES_OFFSET = 0x3180
_PLANET_CREATURE_SPAWNS_OFFSET = 0x32D8
_CREATURE_ROLE_STRIDE = 0x5D8
_CREATURE_ROLE_RARITY_OFFSET = 0x8C
_CREATURE_ROLE_ID_OFFSET = 0x5A0
_CREATURE_ROLE_SEED_OFFSET = 0x5B0
_CREATURE_ROLE_TYPE_OFFSET = 0x5D0
_CREATURE_SPAWN_STRIDE = 0x148
_CREATURE_SPAWN_RESOURCE_FILENAME_OFFSET = 0xA0
_CREATURE_SPAWN_RESOURCE_SEED_OFFSET = 0xC0
_CREATURE_SPAWN_ID_OFFSET = 0xF8
_MAX_PLANETS = 6
_MAX_PLANET_FAUNA = 64
_MAX_VARIABLE_STRING_BYTES = 4096
_HASH_MIX_CONSTANT = 0x9DDFEA08EB382D69
_UINT64_MASK = 0xFFFFFFFFFFFFFFFF

_PLANET_OBJECT_SPAWN_ARRAY_OFFSETS = (0x3C08, 0x3C18, 0x3C28)
_PLANET_OBJECT_SPAWN_CAPACITY_OFFSET = -8
_PLANET_OBJECT_SPAWN_SIZE_OFFSET = -4
_PLANET_OBJECT_SPAWN_STRIDE = 0x70
_PLANET_OBJECT_SPAWN_FILENAME_OFFSET = 0x18
_PLANET_OBJECT_SPAWN_SEED_OFFSET = 0x38
_PLANET_OBJECT_SPAWN_USE_SEED_OFFSET = 0x40
_MAX_PLANET_OBJECT_SPAWNS = 4096
_SCENE_HASH_TYPES = {
    **{scene_hash: 4 for scene_hash in FLORA_SCENE_HASHES},
    **{scene_hash: 5 for scene_hash in MINERAL_SCENE_HASHES},
}

_HANDLE_LOOKUP_MASK = 0x7FFFF
_HANDLE_GENERATION_SHIFT = 19
_MAX_UNIQUE_SUBMITS = 128
_SUBMIT_COOLDOWN_SECONDS = 10.0

_DISCOVERY_NAMES = {3: "Animal", 4: "Flora", 5: "Mineral"}


class _DiscoveryData(ctypes.Structure):
    _fields_ = [
        ("universe_address", ctypes.c_uint64),
        ("keys", ctypes.c_uint64 * 5),
        ("key_count", ctypes.c_uint32),
        ("_padding", ctypes.c_uint32),
        ("discovery_type", ctypes.c_int32),
        ("_tail", ctypes.c_uint32),
    ]


class _MemoryBasicInformation(ctypes.Structure):
    _fields_ = [
        ("BaseAddress", ctypes.c_void_p),
        ("AllocationBase", ctypes.c_void_p),
        ("AllocationProtect", ctypes.c_ulong),
        ("PartitionId", ctypes.c_ushort),
        ("RegionSize", ctypes.c_size_t),
        ("State", ctypes.c_ulong),
        ("Protect", ctypes.c_ulong),
        ("Type", ctypes.c_ulong),
    ]


_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_virtual_query = _kernel32.VirtualQuery
_virtual_query.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(_MemoryBasicInformation),
    ctypes.c_size_t,
]
_virtual_query.restype = ctypes.c_size_t
_get_module_handle = _kernel32.GetModuleHandleW
_get_module_handle.argtypes = [ctypes.c_wchar_p]
_get_module_handle.restype = ctypes.c_void_p
_get_current_process_id = _kernel32.GetCurrentProcessId
_get_current_process_id.argtypes = []
_get_current_process_id.restype = ctypes.c_ulong
_user32 = ctypes.WinDLL("user32", use_last_error=True)
_get_foreground_window = _user32.GetForegroundWindow
_get_foreground_window.argtypes = []
_get_foreground_window.restype = ctypes.c_void_p
_get_window_thread_process_id = _user32.GetWindowThreadProcessId
_get_window_thread_process_id.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_ulong),
]
_get_window_thread_process_id.restype = ctypes.c_ulong


def _event_time() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _nms_module_base() -> int:
    return int(_get_module_handle("NMS.exe") or 0)


def _game_window_is_foreground() -> bool:
    window = _get_foreground_window()
    if not window:
        return False
    process_id = ctypes.c_ulong()
    _get_window_thread_process_id(window, ctypes.byref(process_id))
    return process_id.value == _get_current_process_id()


@dataclass(frozen=True)
class _GameAddresses:
    submit: int
    post_submit: int
    is_known: int
    application_data_pointer: int


def _compile_signature(tokens: list[str] | tuple[str, ...]) -> re.Pattern[bytes]:
    return re.compile(
        b"".join(
            b"." if token in ("?", "??") else re.escape(bytes([int(token, 16)]))
            for token in tokens
        ),
        re.DOTALL,
    )


def _find_unique_pattern(text: bytes, pattern: str) -> int | None:
    tokens = pattern.split()
    detoured = [*_DETOUR_PREFIX, *tokens[len(_DETOUR_PREFIX):]]
    for candidate in (tokens, detoured):
        hits: list[int] = []
        for match in _compile_signature(candidate).finditer(text):
            hits.append(match.start())
            if len(hits) > 1:
                return None
        if hits:
            return hits[0]
    return None


def _read_module_text(module_base: int) -> tuple[int, int, bytes] | None:
    if not _is_readable(module_base, 0x1000):
        return None
    header = ctypes.string_at(module_base, 0x1000)
    pe = struct.unpack_from("<I", header, 0x3C)[0]
    if pe + 0x108 > len(header) or header[pe:pe + 4] != b"PE\0\0":
        return None
    section_count, = struct.unpack_from("<H", header, pe + 6)
    optional_size, = struct.unpack_from("<H", header, pe + 20)
    size_of_image, = struct.unpack_from("<I", header, pe + 24 + 56)
    table = pe + 24 + optional_size
    for index in range(section_count):
        entry = table + index * 40
        if entry + 40 > len(header):
            return None
        name, virtual_size, virtual_address = struct.unpack_from("<8sII", header, entry)
        if name.rstrip(b"\0") != b".text":
            continue
        if virtual_address + virtual_size > size_of_image or not (
            _is_readable(module_base + virtual_address, 1)
            and _is_readable(module_base + virtual_address + virtual_size - 1, 1)
        ):
            return None
        return (
            size_of_image,
            virtual_address,
            ctypes.string_at(module_base + virtual_address, virtual_size),
        )
    return None


def _resolve_game_addresses(module_base: int) -> tuple[_GameAddresses | None, str]:
    module = _read_module_text(module_base)
    if module is None:
        return None, "module_text_unreadable"
    size_of_image, text_rva, text = module
    found: dict[str, int] = {}
    for name, pattern in _GAME_FUNCTION_SIGNATURES.items():
        offset = _find_unique_pattern(text, pattern)
        if offset is None:
            return None, f"{name}_signature_unresolved"
        found[name] = module_base + text_rva + offset
    load = found["IsDiscoveryKnown"] + _IS_DISCOVERY_KNOWN_APPLICATION_LOAD_OFFSET
    pointer = load + 7 + ctypes.c_int32.from_address(load + 3).value
    if not module_base <= pointer < module_base + size_of_image or not _is_readable(
        pointer, 8
    ):
        return None, "application_data_pointer_invalid"
    return (
        _GameAddresses(
            submit=found["SubmitDiscoveryData"],
            post_submit=found["PostSubmitDiscovery"],
            is_known=found["IsDiscoveryKnown"],
            application_data_pointer=pointer,
        ),
        "ok",
    )


def _is_readable(address: int, size: int) -> bool:
    if address <= 0 or size <= 0 or address + size < address:
        return False
    info = _MemoryBasicInformation()
    queried = _virtual_query(
        ctypes.c_void_p(address), ctypes.byref(info), ctypes.sizeof(info)
    )
    if queried != ctypes.sizeof(info) or info.State != 0x1000:
        return False
    if info.Protect & 0x100 or (info.Protect & 0xFF) == 0x01:
        return False
    region_start = int(info.BaseAddress or 0)
    return region_start <= address and address + size <= region_start + int(info.RegionSize)


def _read_u64(address: int) -> int | None:
    if not _is_readable(address, 8):
        return None
    return ctypes.c_uint64.from_address(address).value


def _read_u32(address: int) -> int | None:
    if not _is_readable(address, 4):
        return None
    return ctypes.c_uint32.from_address(address).value


def _read_i32(address: int) -> int | None:
    if not _is_readable(address, 4):
        return None
    return ctypes.c_int32.from_address(address).value


def _is_valid_handle(value: int) -> bool:
    return (value >> _HANDLE_GENERATION_SHIFT) != 0 and (
        value & _HANDLE_LOOKUP_MASK
    ) != _HANDLE_LOOKUP_MASK


@dataclass(frozen=True)
class _SceneCandidate:
    handle: int
    lookup: int
    dense_index: int
    node_pointer: int
    x: float
    y: float
    z: float
    distance: float
    source: str = "scene"


@dataclass(frozen=True)
class _SceneSnapshot:
    target_handle: int
    target_dense_index: int
    target_node_pointer: int
    target_x: float
    target_y: float
    target_z: float
    mapped_entries: int
    live_status_entries: int
    exact_live_entries: int
    candidates: tuple[_SceneCandidate, ...]
    invalid_dense_indices: int = 0
    stale_node_handles: int = 0
    error: str | None = None


@dataclass(frozen=True)
class _FaunaCatalogEntry:
    index: int
    creature_id: str
    resource_filename: str
    seed: int
    creature_type: int
    rarity: int
    data: _DiscoveryData


@dataclass(frozen=True)
class _FaunaCatalogSnapshot:
    planet_pointer: int
    universe_address: int
    entries: tuple[_FaunaCatalogEntry, ...]
    error: str | None = None


@dataclass(frozen=True)
class _PlanetObjectCatalogEntry:
    array_index: int
    slot: int
    resource_name: str
    seed: int
    scene_hash: int
    data: _DiscoveryData


@dataclass(frozen=True)
class _PlanetObjectCatalogSnapshot:
    entries: tuple[_PlanetObjectCatalogEntry, ...]
    array_sizes: tuple[int, ...]
    matching_slots: int
    unseeded_slots: int
    invalid_slots: int
    elapsed_seconds: float
    error: str | None = None
    unclassified_scenes: tuple[tuple[str, int], ...] = ()


@dataclass
class _SubmitBatch:
    sequence: int
    addresses: _GameAddresses
    application_data: int
    discovery_manager: int
    items: list[tuple[_SceneCandidate, _DiscoveryData]]
    nearby_candidates: int
    resolver_attempted: int
    resolver_successful: int
    interesting_resolutions: int
    unique_discoveries: int
    target_resolved: bool
    logged_resolved: int
    type_text: str
    unique_text: str
    already_known: int
    unknown: int
    submit_truncated: bool
    post_submit_context: int = 0
    scan_mode: str = "all"
    submit_interval_seconds: float = 1.0
    sound_feedback: bool = True
    fauna_catalog_entries: int = 0
    fauna_catalog_resolver_matches: int = 0
    fauna_catalog_already_known: int = 0
    fauna_catalog_unknown: int = 0
    fauna_catalog_error: str = "none"
    object_catalog_entries: int = 0
    object_catalog_matching: int = 0
    object_catalog_already_known: int = 0
    object_catalog_unknown: int = 0
    object_catalog_error: str = "none"
    next_index: int = 0
    next_submit_time: float = 0.0
    focus_paused: bool = False
    focus_pauses: int = 0
    submit_returned_true: int = 0
    locally_new_true: int = 0
    accepted: int = 0
    post_submit_calls: int = 0
    accepted_type_counts: dict[str, int] = field(default_factory=dict)


def _snapshot_error(target_handle: int, error: str) -> _SceneSnapshot:
    return _SceneSnapshot(target_handle, -1, 0, 0.0, 0.0, 0.0, 0, 0, 0, (), error=error)


def _collect_scene_candidates(
    handle_map: bytes,
    generations: bytes,
    node_pointers: bytes,
    statuses: bytes,
    transforms: bytes,
    *,
    target_handle: int,
    radius_metres: float,
    node_handle_reader: Callable[[int], int | None],
    center_position: tuple[float, float, float] | None = None,
) -> _SceneSnapshot:
    capacity = len(generations) // 2
    if (
        capacity == 0
        or len(handle_map) != capacity * 4
        or len(node_pointers) != capacity * 8
        or len(statuses) != capacity
        or len(transforms) != capacity * _SCENE_NODE_STRIDE
    ):
        return _snapshot_error(target_handle, "scene_buffer_sizes_invalid")
    if center_position is None:
        if not _is_valid_handle(target_handle):
            return _snapshot_error(target_handle, "target_handle_invalid")
        target_lookup = target_handle & _HANDLE_LOOKUP_MASK
        if target_lookup >= capacity:
            return _snapshot_error(target_handle, "target_lookup_out_of_range")
        target_dense = struct.unpack_from("<i", handle_map, target_lookup * 4)[0]
        if target_dense < 0 or target_dense >= capacity:
            return _snapshot_error(target_handle, "target_dense_index_out_of_range")
        target_generation = struct.unpack_from("<H", generations, target_lookup * 2)[0]
        if target_generation != target_handle >> _HANDLE_GENERATION_SHIFT:
            return _snapshot_error(target_handle, "target_generation_mismatch")
        if statuses[target_dense] != _SCENE_NODE_STATUS_LIVE:
            return _snapshot_error(target_handle, "target_not_live")
        target_node_pointer = struct.unpack_from("<Q", node_pointers, target_dense * 8)[0]
        if node_handle_reader(target_node_pointer) != target_handle:
            return _snapshot_error(target_handle, "target_node_handle_mismatch")
        target_position_offset = (
            target_dense * _SCENE_NODE_STRIDE + _SCENE_NODE_POSITION_OFFSET
        )
        target_x, target_y, target_z = struct.unpack_from(
            "<fff", transforms, target_position_offset
        )
    else:
        target_dense = -1
        target_node_pointer = 0
        target_x, target_y, target_z = center_position
    if not all(math.isfinite(v) for v in (target_x, target_y, target_z)):
        return _snapshot_error(target_handle, "target_position_not_finite")

    mapped_entries = 0
    live_status_entries = 0
    exact_live_entries = 0
    invalid_dense_indices = 0
    stale_node_handles = 0
    radius_squared = radius_metres * radius_metres
    candidates: list[_SceneCandidate] = []

    for lookup in range(capacity):
        generation = struct.unpack_from("<H", generations, lookup * 2)[0]
        if generation == 0:
            continue
        dense_index = struct.unpack_from("<i", handle_map, lookup * 4)[0]
        if dense_index < 0:
            continue
        mapped_entries += 1
        if dense_index >= capacity:
            invalid_dense_indices += 1
            continue
        if statuses[dense_index] != _SCENE_NODE_STATUS_LIVE:
            continue
        live_status_entries += 1

        handle = (generation << _HANDLE_GENERATION_SHIFT) | lookup
        node_pointer = struct.unpack_from("<Q", node_pointers, dense_index * 8)[0]
        if node_handle_reader(node_pointer) != handle:
            stale_node_handles += 1
            continue
        exact_live_entries += 1

        position_offset = dense_index * _SCENE_NODE_STRIDE + _SCENE_NODE_POSITION_OFFSET
        x, y, z = struct.unpack_from("<fff", transforms, position_offset)
        if not all(math.isfinite(v) for v in (x, y, z)):
            continue
        dx, dy, dz = x - target_x, y - target_y, z - target_z
        distance_squared = dx * dx + dy * dy + dz * dz
        if distance_squared > radius_squared:
            continue
        candidates.append(
            _SceneCandidate(
                handle, lookup, dense_index, node_pointer,
                x, y, z, math.sqrt(distance_squared),
            )
        )

    candidates.sort(key=lambda item: (item.distance, item.handle))
    return _SceneSnapshot(
        target_handle=target_handle,
        target_dense_index=target_dense,
        target_node_pointer=target_node_pointer,
        target_x=target_x,
        target_y=target_y,
        target_z=target_z,
        mapped_entries=mapped_entries,
        live_status_entries=live_status_entries,
        exact_live_entries=exact_live_entries,
        candidates=tuple(candidates),
        invalid_dense_indices=invalid_dense_indices,
        stale_node_handles=stale_node_handles,
    )


def _hash_mix_64(first: int, second: int) -> int:
    first &= _UINT64_MASK
    second &= _UINT64_MASK
    value = ((first ^ second) * _HASH_MIX_CONSTANT) & _UINT64_MASK
    mixed = (
        ((value >> 47) ^ value ^ first) * _HASH_MIX_CONSTANT
    ) & _UINT64_MASK
    return (((mixed >> 47) ^ mixed) * _HASH_MIX_CONSTANT) & _UINT64_MASK


def _normalise_scene_filename(filename: str) -> str:
    stem = filename.upper().split(".", 1)[0]
    return f"{stem}.SCENE.MBIN"


def _djb2_64(value: str) -> int:
    result = 0x1505
    for byte in value.encode("ascii"):
        result = (result * 0x21 + byte) & _UINT64_MASK
    return result


def _build_fauna_discovery_data(
    universe_address: int,
    creature_id: bytes | str,
    resource_filename: str,
    seed: int,
    creature_type: int,
    rarity: int,
) -> _DiscoveryData:
    raw_id = creature_id.encode("ascii") if isinstance(creature_id, str) else creature_id
    raw_id = raw_id.split(b"\0", 1)[0]
    if not raw_id or len(raw_id) > 16:
        raise ValueError("creature_id_invalid")
    packed_id = raw_id.ljust(16, b"\0")
    id_low = int.from_bytes(packed_id[:8], "little")
    id_high = int.from_bytes(packed_id[8:16], "little")
    normalised_filename = _normalise_scene_filename(resource_filename)
    if normalised_filename == ".SCENE.MBIN":
        raise ValueError("creature_resource_filename_empty")

    data = _DiscoveryData()
    data.universe_address = universe_address & _UINT64_MASK
    data.keys[0] = seed & _UINT64_MASK
    data.keys[1] = _djb2_64(normalised_filename)
    data.keys[2] = _hash_mix_64(_hash_mix_64(id_low, id_high), seed)
    data.keys[3] = _hash_mix_64(
        _hash_mix_64(universe_address, creature_type), rarity
    )
    data.key_count = 4
    data.discovery_type = 3
    return data


def _read_variable_string(address: int) -> str | None:
    array_pointer = _read_u64(address)
    size = _read_u32(address + 8)
    if array_pointer is None or size is None:
        return None
    if array_pointer == 0 or size == 0:
        return ""
    if size > _MAX_VARIABLE_STRING_BYTES or not _is_readable(array_pointer, size):
        return None
    raw = ctypes.string_at(array_pointer, size).split(b"\0", 1)[0]
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError:
        return None


def _fauna_catalog_error(error: str) -> _FaunaCatalogSnapshot:
    return _FaunaCatalogSnapshot(0, 0, (), error)


def _select_game_layout(
    application_data: int,
) -> tuple[_GameLayout | None, str]:
    for layout in _GAME_LAYOUTS:
        current_universe_address = _read_u64(
            application_data + layout.current_planet_address_offset
        )
        solar_system = _read_u64(
            application_data + layout.solar_system_pointer_offset
        )
        if not current_universe_address or not solar_system:
            continue
        planet_count = _read_i32(solar_system + _SOLAR_PLANET_COUNT_OFFSET)
        if planet_count is None or not 0 < planet_count <= _MAX_PLANETS:
            continue
        for index in range(planet_count):
            candidate = solar_system + _SOLAR_PLANETS_OFFSET + index * _PLANET_STRIDE
            if (
                _read_u64(candidate + _PLANET_DISCOVERY_DATA_OFFSET)
                == current_universe_address
            ):
                return layout, "ok"
    return None, "planet_catalog_context_unreadable"


def _read_current_planet_fauna_catalog(
    application_data: int,
    layout: _GameLayout,
) -> _FaunaCatalogSnapshot:
    current_universe_address = _read_u64(
        application_data + layout.current_planet_address_offset
    )
    solar_system = _read_u64(
        application_data + layout.solar_system_pointer_offset
    )
    if current_universe_address is None or solar_system is None or solar_system == 0:
        return _fauna_catalog_error("planet_catalog_context_unreadable")

    planet_count = _read_i32(solar_system + _SOLAR_PLANET_COUNT_OFFSET)
    if planet_count is None or not 0 < planet_count <= _MAX_PLANETS:
        return _fauna_catalog_error("planet_count_invalid")

    planet_pointer = 0
    for index in range(planet_count):
        candidate = solar_system + _SOLAR_PLANETS_OFFSET + index * _PLANET_STRIDE
        candidate_address = _read_u64(candidate + _PLANET_DISCOVERY_DATA_OFFSET)
        if candidate_address == current_universe_address:
            planet_pointer = candidate
            break
    if planet_pointer == 0:
        return _fauna_catalog_error("not_on_generated_planet")

    planet_data = planet_pointer + _PLANET_DATA_OFFSET
    roles_header = planet_data + _PLANET_CREATURE_ROLES_OFFSET
    spawns_header = planet_data + _PLANET_CREATURE_SPAWNS_OFFSET
    roles_pointer = _read_u64(roles_header)
    roles_count = _read_u32(roles_header + 8)
    spawns_pointer = _read_u64(spawns_header)
    spawns_count = _read_u32(spawns_header + 8)
    if None in (roles_pointer, roles_count, spawns_pointer, spawns_count):
        return _fauna_catalog_error("fauna_array_headers_unreadable")
    if roles_count != spawns_count or roles_count > _MAX_PLANET_FAUNA:
        return _fauna_catalog_error("fauna_array_counts_invalid")
    if roles_count == 0:
        return _FaunaCatalogSnapshot(
            planet_pointer, current_universe_address, ()
        )
    if not roles_pointer or not spawns_pointer:
        return _fauna_catalog_error("fauna_array_pointers_null")
    if not _is_readable(roles_pointer, roles_count * _CREATURE_ROLE_STRIDE):
        return _fauna_catalog_error("creature_roles_unreadable")
    if not _is_readable(spawns_pointer, spawns_count * _CREATURE_SPAWN_STRIDE):
        return _fauna_catalog_error("creature_spawns_unreadable")

    entries: list[_FaunaCatalogEntry] = []
    for index in range(roles_count):
        role_address = roles_pointer + index * _CREATURE_ROLE_STRIDE
        spawn_address = spawns_pointer + index * _CREATURE_SPAWN_STRIDE
        role_id = ctypes.string_at(role_address + _CREATURE_ROLE_ID_OFFSET, 16)
        spawn_id = ctypes.string_at(spawn_address + _CREATURE_SPAWN_ID_OFFSET, 16)
        role_seed = _read_u64(role_address + _CREATURE_ROLE_SEED_OFFSET)
        spawn_seed = _read_u64(
            spawn_address + _CREATURE_SPAWN_RESOURCE_SEED_OFFSET
        )
        creature_type = _read_i32(role_address + _CREATURE_ROLE_TYPE_OFFSET)
        rarity = _read_i32(role_address + _CREATURE_ROLE_RARITY_OFFSET)
        resource_filename = _read_variable_string(
            spawn_address + _CREATURE_SPAWN_RESOURCE_FILENAME_OFFSET
        )
        if None in (role_seed, spawn_seed, creature_type, rarity, resource_filename):
            return _fauna_catalog_error("fauna_entry_unreadable")
        if role_id != spawn_id or role_seed != spawn_seed:
            return _fauna_catalog_error("fauna_role_spawn_mismatch")
        creature_id_bytes = role_id.split(b"\0", 1)[0]
        try:
            creature_id_text = creature_id_bytes.decode("ascii")
            data = _build_fauna_discovery_data(
                current_universe_address,
                creature_id_bytes,
                resource_filename,
                role_seed,
                creature_type,
                rarity,
            )
        except (UnicodeDecodeError, ValueError):
            return _fauna_catalog_error("fauna_entry_invalid")
        entries.append(
            _FaunaCatalogEntry(
                index=index,
                creature_id=creature_id_text,
                resource_filename=_normalise_scene_filename(resource_filename),
                seed=role_seed,
                creature_type=creature_type,
                rarity=rarity,
                data=data,
            )
        )

    return _FaunaCatalogSnapshot(
        planet_pointer,
        current_universe_address,
        tuple(entries),
    )


def _build_planet_object_discovery_data(
    universe_address: int,
    seed: int,
    scene_hash: int,
    discovery_type: int,
) -> _DiscoveryData:
    if discovery_type not in (4, 5):
        raise ValueError("planet_object_discovery_type_invalid")
    data = _DiscoveryData()
    data.universe_address = universe_address & _UINT64_MASK
    data.keys[0] = seed & _UINT64_MASK
    data.keys[1] = scene_hash & _UINT64_MASK
    data.key_count = 2
    data.discovery_type = discovery_type
    return data


def _planet_object_catalog_error(
    error: str,
    array_sizes: list[int],
    started: float,
) -> _PlanetObjectCatalogSnapshot:
    return _PlanetObjectCatalogSnapshot(
        (), tuple(array_sizes), 0, 0, 0, time.perf_counter() - started, error
    )


def _read_planet_object_catalog(
    planet_pointer: int,
    universe_address: int,
) -> _PlanetObjectCatalogSnapshot:
    started = time.perf_counter()
    array_sizes: list[int] = []
    matching_slots = 0
    unseeded_slots = 0
    invalid_slots = 0
    unclassified: dict[str, int] = {}
    unique: dict[
        tuple[int, int, tuple[int, ...]], _PlanetObjectCatalogEntry
    ] = {}
    for array_index, array_offset in enumerate(_PLANET_OBJECT_SPAWN_ARRAY_OFFSETS):
        header = planet_pointer + array_offset
        capacity = _read_u32(header + _PLANET_OBJECT_SPAWN_CAPACITY_OFFSET)
        size = _read_u32(header + _PLANET_OBJECT_SPAWN_SIZE_OFFSET)
        elements = _read_u64(header)
        if None in (capacity, size, elements):
            return _planet_object_catalog_error(
                "spawn_array_header_unreadable", array_sizes, started
            )
        if size > capacity or size > _MAX_PLANET_OBJECT_SPAWNS:
            return _planet_object_catalog_error(
                "spawn_array_size_invalid", array_sizes, started
            )
        array_sizes.append(size)
        if size == 0:
            continue
        if not elements or not _is_readable(
            elements, size * _PLANET_OBJECT_SPAWN_STRIDE
        ):
            return _planet_object_catalog_error(
                "spawn_array_unreadable", array_sizes, started
            )

        for slot in range(size):
            element = elements + slot * _PLANET_OBJECT_SPAWN_STRIDE
            filename = _read_variable_string(
                element + _PLANET_OBJECT_SPAWN_FILENAME_OFFSET
            )
            if filename is None:
                invalid_slots += 1
                continue
            resource_name = filename.replace("\\", "/").upper()
            if not resource_name.endswith(".SCENE.MBIN"):
                continue
            scene_hash = _djb2_64(resource_name)
            discovery_type = _SCENE_HASH_TYPES.get(scene_hash)
            if discovery_type is None:
                unclassified[resource_name] = unclassified.get(resource_name, 0) + 1
                continue
            matching_slots += 1
            use_seed = ctypes.c_ubyte.from_address(
                element + _PLANET_OBJECT_SPAWN_USE_SEED_OFFSET
            ).value
            if use_seed != 1:
                unseeded_slots += 1
                continue
            seed = ctypes.c_uint64.from_address(
                element + _PLANET_OBJECT_SPAWN_SEED_OFFSET
            ).value
            data = _build_planet_object_discovery_data(
                universe_address, seed, scene_hash, discovery_type
            )
            unique.setdefault(
                _discovery_fingerprint(data),
                _PlanetObjectCatalogEntry(
                    array_index=array_index,
                    slot=slot,
                    resource_name=resource_name,
                    seed=seed,
                    scene_hash=scene_hash,
                    data=data,
                ),
            )

    if not any(array_sizes):
        return _planet_object_catalog_error(
            "spawn_arrays_empty", array_sizes, started
        )
    return _PlanetObjectCatalogSnapshot(
        entries=tuple(unique.values()),
        array_sizes=tuple(array_sizes),
        matching_slots=matching_slots,
        unseeded_slots=unseeded_slots,
        invalid_slots=invalid_slots,
        elapsed_seconds=time.perf_counter() - started,
        unclassified_scenes=tuple(unclassified.items()),
    )


def _discovery_fingerprint(data: _DiscoveryData) -> tuple[int, int, tuple[int, ...]]:
    count = min(int(data.key_count), 3)
    return (
        int(data.universe_address),
        int(data.discovery_type),
        tuple(int(data.keys[index]) for index in range(count)),
    )


class DiscoveryProbe(Mod):
    __author__ = "NMSDiscoveryLab"
    __description__ = "Full planet fauna, flora, and mineral discovery on F10"
    __version__ = "1.1.1"

    def __init__(self):
        super().__init__()
        self._stage6_lock = threading.Lock()
        self._stage6_pending_sequence = 0
        self._stage6_pending_settings = INITIAL_SETTINGS
        self._stage6_active_sequence = 0
        self._stage6_sequence = 0
        self._stage6_last_request_time = 0.0
        self._stage6_batch: _SubmitBatch | None = None
        self._game_addresses_resolved = False
        self._game_addresses: _GameAddresses | None = None
        self._game_address_error = "unresolved"
        logger.info("Discovery Probe loaded")
        logger.info("settings_path=%s", settings_path())
        logger.info(
            "profile=signature-resolved stage=9 mode=full-planet-catalog-submit "
            "version=%s object_source=planet-spawn-arrays focus_guard=enabled "
            "flora_scene_hashes=%d mineral_scene_hashes=%d "
            "max_unique_submits=%d settings_mode=%s "
            "submit_interval_seconds=%.3f sound_feedback=%s hotkey=%s "
            "hotkey_enabled=%s submit_cooldown_seconds=%.1f "
            "submit=enabled save_mutation=enabled",
            self.__version__,
            len(FLORA_SCENE_HASHES),
            len(MINERAL_SCENE_HASHES),
            _MAX_UNIQUE_SUBMITS,
            INITIAL_SETTINGS.scan_mode,
            INITIAL_SETTINGS.submit_interval_seconds,
            INITIAL_SETTINGS.sound_feedback,
            INITIAL_SETTINGS.scan_key.upper(),
            INITIAL_SETTINGS.enable_hotkey,
            _SUBMIT_COOLDOWN_SECONDS,
        )

    @on_key_release(INITIAL_SETTINGS.scan_key)
    def request_nearby_discovery_submit(self) -> None:
        settings = load_settings()
        if not settings.enable_hotkey:
            logger.warning(
                "event=PlanetDiscoverySubmitRequestIgnored timestamp=%s "
                "reason=hotkey_disabled hotkey=%s",
                _event_time(), INITIAL_SETTINGS.scan_key.upper(),
            )
            return
        now = time.monotonic()
        with self._stage6_lock:
            if self._stage6_pending_sequence:
                reason = "submit_already_pending"
                sequence = self._stage6_pending_sequence
            elif self._stage6_active_sequence:
                reason = "submit_in_progress"
                sequence = self._stage6_active_sequence
            elif now - self._stage6_last_request_time < _SUBMIT_COOLDOWN_SECONDS:
                reason = "cooldown"
                sequence = self._stage6_sequence
            else:
                reason = ""
                self._stage6_sequence += 1
                sequence = self._stage6_sequence
                self._stage6_pending_sequence = sequence
                self._stage6_pending_settings = settings
                self._stage6_last_request_time = now
        if reason:
            logger.warning(
                "event=NearbyDiscoverySubmitRequestIgnored timestamp=%s sequence=%d "
                "reason=%s center_source=player submit=enabled "
                "save_mutation=enabled",
                _event_time(), sequence, reason,
            )
            return
        logger.warning(
            "event=PlanetDiscoverySubmitRequested timestamp=%s sequence=%d "
            "scope=full_planet scan_mode=%s interval_seconds=%.3f "
            "sound_feedback=%s submit=enabled save_mutation=enabled",
            _event_time(), sequence, settings.scan_mode,
            settings.submit_interval_seconds, settings.sound_feedback,
        )

    @nms.cGcScanManager.UpdateScannableMarkers.after
    def submit_nearby_scene_nodes(self, this: Any) -> None:
        if self._stage6_batch is not None:
            try:
                self._submit_next_queued_discovery()
            except Exception:
                logger.exception("Queued nearby discovery submit failed")
                self._stage6_batch = None
                self._release_stage6_attempt()

        with self._stage6_lock:
            sequence = self._stage6_pending_sequence
            settings = self._stage6_pending_settings
            self._stage6_pending_sequence = 0
            if sequence:
                self._stage6_active_sequence = sequence
            target_handle = 0
        if not sequence:
            return

        module_base = _nms_module_base()
        try:
            if not self._game_addresses_resolved:
                started = time.perf_counter()
                self._game_addresses, self._game_address_error = (
                    _resolve_game_addresses(module_base)
                )
                self._game_addresses_resolved = True
                resolved = self._game_addresses
                logger.warning(
                    "event=GameAddressesResolved timestamp=%s result=%s "
                    "submit_rva=0x%X post_submit_rva=0x%X is_known_rva=0x%X "
                    "application_data_pointer_rva=0x%X elapsed_seconds=%.3f",
                    _event_time(), self._game_address_error,
                    (resolved.submit - module_base) if resolved else 0,
                    (resolved.post_submit - module_base) if resolved else 0,
                    (resolved.is_known - module_base) if resolved else 0,
                    (resolved.application_data_pointer - module_base) if resolved else 0,
                    time.perf_counter() - started,
                )
            addresses = self._game_addresses
            if addresses is None:
                logger.error(
                    "event=PlanetDiscoverySubmitBlocked timestamp=%s sequence=%d "
                    "error=%s submit=disabled save_mutation=disabled",
                    _event_time(), sequence, self._game_address_error,
                )
                self._release_stage6_attempt()
                return
            application_data = _read_u64(addresses.application_data_pointer)
            if not application_data:
                raise RuntimeError("application_data_unreadable")
            layout, layout_result = _select_game_layout(application_data)
            if layout is None:
                logger.warning(
                    "event=GameLayoutResolutionFailed timestamp=%s sequence=%d "
                    "error=%s profiles=%s submit=disabled save_mutation=disabled",
                    _event_time(), sequence, layout_result,
                    ",".join(candidate.profile for candidate in _GAME_LAYOUTS),
                )
                self._release_stage6_attempt()
                return
            logger.warning(
                "event=GameLayoutResolved timestamp=%s sequence=%d profile=%s "
                "current_planet_offset=0x%X solar_system_offset=0x%X "
                "discovery_manager_offset=0x%X lookup_context_offset=0x%X "
                "post_submit_context_offset=0x%X",
                _event_time(), sequence, layout.profile,
                layout.current_planet_address_offset,
                layout.solar_system_pointer_offset,
                layout.discovery_manager_offset,
                layout.discovery_lookup_context_offset,
                layout.post_submit_context_offset,
            )
            unique: dict[
                tuple[int, int, tuple[int, ...]], tuple[_SceneCandidate, _DiscoveryData]
            ] = {}
            fauna_catalog = _read_current_planet_fauna_catalog(
                application_data, layout
            )
            fauna_catalog_fingerprints: set[
                tuple[int, int, tuple[int, ...]]
            ] = set()
            if fauna_catalog.error:
                logger.warning(
                    "event=PlanetFaunaCatalogSkipped timestamp=%s sequence=%d "
                    "error=%s submit=disabled save_mutation=disabled",
                    _event_time(), sequence, fauna_catalog.error,
                )
                self._release_stage6_attempt()
                return
            else:
                for entry in fauna_catalog.entries:
                    fingerprint = _discovery_fingerprint(entry.data)
                    fauna_catalog_fingerprints.add(fingerprint)
                    catalog_candidate = _SceneCandidate(
                        handle=0,
                        lookup=entry.index,
                        dense_index=-1,
                        node_pointer=0,
                        x=0.0,
                        y=0.0,
                        z=0.0,
                        distance=0.0,
                        source="fauna_catalog",
                    )
                    unique.setdefault(
                        fingerprint, (catalog_candidate, entry.data)
                    )
                    logger.info(
                        "event=PlanetFaunaCatalogCandidate sequence=%d index=%d "
                        "creature_id=%s resource=%s seed=%d creature_type=%d "
                        "rarity=%d universe_address=%d key_count=%d keys=%s "
                        "resolver_match=%s submit=pending save_mutation=enabled",
                        sequence, entry.index, entry.creature_id,
                        entry.resource_filename, entry.seed, entry.creature_type,
                        entry.rarity, int(entry.data.universe_address),
                        int(entry.data.key_count),
                        ":".join(
                            f"{int(entry.data.keys[index]):016X}"
                            for index in range(int(entry.data.key_count))
                        ),
                        False,
                    )
                logger.warning(
                    "event=PlanetFaunaCatalogReady timestamp=%s sequence=%d "
                    "planet=0x%X universe_address=%d entries=%d "
                    "submit=enabled save_mutation=enabled",
                    _event_time(), sequence, fauna_catalog.planet_pointer,
                    fauna_catalog.universe_address, len(fauna_catalog.entries),
                )

            if settings.scan_mode == "all":
                object_catalog = _read_planet_object_catalog(
                    fauna_catalog.planet_pointer, fauna_catalog.universe_address
                )
            else:
                object_catalog = _PlanetObjectCatalogSnapshot(
                    entries=(),
                    array_sizes=(),
                    matching_slots=0,
                    unseeded_slots=0,
                    invalid_slots=0,
                    elapsed_seconds=0.0,
                )
            object_catalog_fingerprints: set[
                tuple[int, int, tuple[int, ...]]
            ] = set()
            array_sizes_text = "/".join(
                str(size) for size in object_catalog.array_sizes
            ) or "none"
            if settings.scan_mode == "fauna":
                logger.warning(
                    "event=PlanetObjectCatalogDisabled timestamp=%s sequence=%d "
                    "reason=scan_mode_fauna submit=disabled save_mutation=disabled",
                    _event_time(), sequence,
                )
            elif object_catalog.error:
                logger.warning(
                    "event=PlanetObjectCatalogSkipped timestamp=%s sequence=%d "
                    "planet=0x%X spawn_arrays=%s elapsed_seconds=%.3f "
                    "error=%s submit=disabled save_mutation=disabled",
                    _event_time(), sequence, fauna_catalog.planet_pointer,
                    array_sizes_text, object_catalog.elapsed_seconds,
                    object_catalog.error,
                )
            else:
                for entry in object_catalog.entries:
                    fingerprint = _discovery_fingerprint(entry.data)
                    object_catalog_fingerprints.add(fingerprint)
                    catalog_candidate = _SceneCandidate(
                        handle=0,
                        lookup=entry.slot,
                        dense_index=-1,
                        node_pointer=0,
                        x=0.0,
                        y=0.0,
                        z=0.0,
                        distance=0.0,
                        source="planet_object_catalog",
                    )
                    unique.setdefault(fingerprint, (catalog_candidate, entry.data))
                    logger.info(
                        "event=PlanetObjectCatalogCandidate sequence=%d "
                        "array=%d slot=%d resource=%s seed=%d "
                        "scene_hash=%016X universe_address=%d type=%d "
                        "type_name=%s keys=%016X:%016X submit=pending "
                        "save_mutation=enabled",
                        sequence, entry.array_index, entry.slot,
                        entry.resource_name, entry.seed, entry.scene_hash,
                        int(entry.data.universe_address),
                        int(entry.data.discovery_type),
                        _DISCOVERY_NAMES[int(entry.data.discovery_type)],
                        int(entry.data.keys[0]), int(entry.data.keys[1]),
                    )
                for resource_name, slots in object_catalog.unclassified_scenes:
                    logger.info(
                        "event=PlanetObjectCatalogUnclassifiedScene sequence=%d "
                        "resource=%s slots=%d",
                        sequence, resource_name, slots,
                    )
                logger.warning(
                    "event=PlanetObjectCatalogReady timestamp=%s sequence=%d "
                    "planet=0x%X spawn_arrays=%s matching=%d unseeded=%d "
                    "invalid=%d unclassified_scenes=%d entries=%d "
                    "elapsed_seconds=%.3f submit=enabled save_mutation=enabled",
                    _event_time(), sequence, fauna_catalog.planet_pointer,
                    array_sizes_text, object_catalog.matching_slots,
                    object_catalog.unseeded_slots, object_catalog.invalid_slots,
                    len(object_catalog.unclassified_scenes),
                    len(object_catalog.entries), object_catalog.elapsed_seconds,
                )

            unique_type_counts: dict[str, int] = {}
            for fingerprint in unique:
                name = _DISCOVERY_NAMES.get(fingerprint[1], f"Other({fingerprint[1]})")
                unique_type_counts[name] = unique_type_counts.get(name, 0) + 1
            unique_text = ",".join(
                f"{name}:{count}" for name, count in sorted(unique_type_counts.items())
            ) or "none"

            discovery_manager = _read_u64(
                application_data + layout.discovery_manager_offset
            )
            if not discovery_manager:
                raise RuntimeError("discovery_manager_unreadable")
            is_known_type = ctypes.CFUNCTYPE(
                ctypes.c_bool,
                ctypes.c_uint64,
                ctypes.POINTER(_DiscoveryData),
            )
            is_known = is_known_type(addresses.is_known)

            unknown: list[tuple[_SceneCandidate, _DiscoveryData]] = []
            already_known = 0
            fauna_catalog_already_known = 0
            fauna_catalog_unknown = 0
            object_catalog_already_known = 0
            object_catalog_unknown = 0
            lookup_context = (
                application_data + layout.discovery_lookup_context_offset
            )
            for fingerprint, (candidate, data) in unique.items():
                if is_known(lookup_context, ctypes.byref(data)):
                    already_known += 1
                    if fingerprint in fauna_catalog_fingerprints:
                        fauna_catalog_already_known += 1
                    if fingerprint in object_catalog_fingerprints:
                        object_catalog_already_known += 1
                else:
                    unknown.append((candidate, data))
                    if fingerprint in fauna_catalog_fingerprints:
                        fauna_catalog_unknown += 1
                    if fingerprint in object_catalog_fingerprints:
                        object_catalog_unknown += 1

            queued_items = unknown[:_MAX_UNIQUE_SUBMITS]
            self._stage6_batch = _SubmitBatch(
                sequence=sequence,
                addresses=addresses,
                application_data=application_data,
                discovery_manager=discovery_manager,
                post_submit_context=(
                    application_data + layout.post_submit_context_offset
                ),
                items=queued_items,
                nearby_candidates=0,
                resolver_attempted=0,
                resolver_successful=0,
                interesting_resolutions=0,
                unique_discoveries=len(unique),
                target_resolved=False,
                logged_resolved=0,
                type_text=unique_text,
                unique_text=unique_text,
                already_known=already_known,
                unknown=len(unknown),
                submit_truncated=len(unknown) > _MAX_UNIQUE_SUBMITS,
                scan_mode=settings.scan_mode,
                submit_interval_seconds=settings.submit_interval_seconds,
                sound_feedback=settings.sound_feedback,
                fauna_catalog_entries=len(fauna_catalog.entries),
                fauna_catalog_resolver_matches=0,
                fauna_catalog_already_known=fauna_catalog_already_known,
                fauna_catalog_unknown=fauna_catalog_unknown,
                fauna_catalog_error=fauna_catalog.error or "none",
                object_catalog_entries=len(object_catalog.entries),
                object_catalog_matching=object_catalog.matching_slots,
                object_catalog_already_known=object_catalog_already_known,
                object_catalog_unknown=object_catalog_unknown,
                object_catalog_error=object_catalog.error or "none",
                next_submit_time=time.monotonic(),
            )
            logger.warning(
                "event=PlanetDiscoverySubmitQueueReady timestamp=%s sequence=%d "
                "queued=%d unknown=%d fauna_catalog_entries=%d "
                "fauna_catalog_known=%d fauna_catalog_unknown=%d "
                "object_catalog_entries=%d object_catalog_known=%d "
                "object_catalog_unknown=%d "
                "scan_mode=%s interval_seconds=%.3f sound_feedback=%s "
                "submit=enabled save_mutation=enabled",
                _event_time(), sequence, len(queued_items), len(unknown),
                len(fauna_catalog.entries), fauna_catalog_already_known,
                fauna_catalog_unknown,
                len(object_catalog.entries), object_catalog_already_known,
                object_catalog_unknown,
                settings.scan_mode, settings.submit_interval_seconds,
                settings.sound_feedback,
            )
            if not queued_items:
                self._finish_submit_batch()
        except Exception:
            logger.exception("Nearby discovery submit callback failed")
            self._stage6_batch = None
            self._release_stage6_attempt()

    def _submit_next_queued_discovery(self) -> None:
        batch = self._stage6_batch
        if batch is None or time.monotonic() < batch.next_submit_time:
            return
        if not _game_window_is_foreground():
            if not batch.focus_paused:
                batch.focus_paused = True
                batch.focus_pauses += 1
                logger.warning(
                    "event=PlanetDiscoverySubmitPaused timestamp=%s sequence=%d "
                    "item=%d total=%d reason=game_not_foreground "
                    "save_mutation=enabled",
                    _event_time(), batch.sequence, batch.next_index,
                    len(batch.items),
                )
            return
        if batch.focus_paused:
            batch.focus_paused = False
            batch.next_submit_time = (
                time.monotonic() + batch.submit_interval_seconds
            )
            logger.warning(
                "event=PlanetDiscoverySubmitResumed timestamp=%s sequence=%d "
                "item=%d total=%d save_mutation=enabled",
                _event_time(), batch.sequence, batch.next_index, len(batch.items),
            )
            return
        current_application_data = _read_u64(
            batch.addresses.application_data_pointer
        )
        if current_application_data != batch.application_data:
            raise RuntimeError("application_data_changed_during_submit_queue")

        candidate, data = batch.items[batch.next_index]
        submit_type = ctypes.CFUNCTYPE(
            ctypes.c_bool,
            ctypes.c_uint64,
            ctypes.POINTER(_DiscoveryData),
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_bool),
            ctypes.c_bool,
        )
        post_submit_type = ctypes.CFUNCTYPE(
            ctypes.c_uint32,
            ctypes.c_uint64,
            ctypes.POINTER(_DiscoveryData),
            ctypes.c_bool,
        )
        submit = submit_type(batch.addresses.submit)
        post_submit = post_submit_type(batch.addresses.post_submit)

        locally_new = ctypes.c_bool(False)
        timestamp = int(time.time()) & 0xFFFFFFFF
        result = bool(
            submit(
                batch.discovery_manager,
                ctypes.byref(data),
                timestamp,
                ctypes.byref(locally_new),
                True,
            )
        )
        if result:
            batch.submit_returned_true += 1
        if locally_new.value:
            batch.locally_new_true += 1
        accepted_this = result or locally_new.value
        post_result: int | str = "skipped"
        if accepted_this:
            batch.accepted += 1
            discovery_name = _DISCOVERY_NAMES[int(data.discovery_type)]
            batch.accepted_type_counts[discovery_name] = (
                batch.accepted_type_counts.get(discovery_name, 0) + 1
            )
            post_result = int(
                post_submit(
                    batch.post_submit_context,
                    ctypes.byref(data),
                    not batch.sound_feedback,
                )
            )
            batch.post_submit_calls += 1

        batch.next_index += 1
        remaining = len(batch.items) - batch.next_index
        logger.warning(
            "event=NearbyDiscoverySubmit sequence=%d item=%d total=%d remaining=%d "
            "source=%s handle=0x%X distance=%.3f type=%d type_name=%s timestamp=%d "
            "result=%s locally_new=%s accepted=%s post_result=%s "
            "sound_feedback=%s "
            "save_mutation=enabled",
            batch.sequence, batch.next_index, len(batch.items), remaining,
            candidate.source, candidate.handle, candidate.distance,
            int(data.discovery_type),
            _DISCOVERY_NAMES[int(data.discovery_type)], timestamp, result,
            locally_new.value, accepted_this, post_result, batch.sound_feedback,
        )
        if remaining:
            batch.next_submit_time = (
                time.monotonic() + batch.submit_interval_seconds
            )
        else:
            self._finish_submit_batch()

    def _finish_submit_batch(self) -> None:
        batch = self._stage6_batch
        if batch is None:
            return
        accepted_text = ",".join(
            f"{name}:{count}"
            for name, count in sorted(batch.accepted_type_counts.items())
        ) or "none"
        logger.warning(
            "event=NearbyDiscoverySubmitEnd timestamp=%s sequence=%d "
            "nearby_candidates=%d resolver_attempted=%d resolver_successful=%d "
            "interesting_resolutions=%d unique_discoveries=%d "
            "target_resolved=%s logged_resolved=%d type_counts=%s "
            "unique_type_counts=%s already_known=%d unknown=%d "
            "fauna_catalog_entries=%d fauna_catalog_resolver_matches=%d "
            "fauna_catalog_already_known=%d fauna_catalog_unknown=%d "
            "fauna_catalog_error=%s "
            "object_catalog_entries=%d object_catalog_matching=%d "
            "object_catalog_already_known=%d object_catalog_unknown=%d "
            "object_catalog_error=%s "
            "submit_attempted=%d submit_truncated=%s submit_returned_true=%d "
            "locally_new_true=%d accepted=%d post_submit_calls=%d "
            "accepted_type_counts=%s focus_pauses=%d scan_mode=%s "
            "interval_seconds=%.3f sound_feedback=%s "
            "submit=enabled save_mutation=enabled",
            _event_time(), batch.sequence, batch.nearby_candidates,
            batch.resolver_attempted, batch.resolver_successful,
            batch.interesting_resolutions, batch.unique_discoveries,
            batch.target_resolved, batch.logged_resolved, batch.type_text,
            batch.unique_text, batch.already_known, batch.unknown,
            batch.fauna_catalog_entries, batch.fauna_catalog_resolver_matches,
            batch.fauna_catalog_already_known, batch.fauna_catalog_unknown,
            batch.fauna_catalog_error,
            batch.object_catalog_entries, batch.object_catalog_matching,
            batch.object_catalog_already_known, batch.object_catalog_unknown,
            batch.object_catalog_error,
            len(batch.items), batch.submit_truncated, batch.submit_returned_true,
            batch.locally_new_true, batch.accepted, batch.post_submit_calls,
            accepted_text, batch.focus_pauses, batch.scan_mode,
            batch.submit_interval_seconds, batch.sound_feedback,
        )
        self._stage6_batch = None
        self._release_stage6_attempt()

    def _release_stage6_attempt(self) -> None:
        with self._stage6_lock:
            self._stage6_active_sequence = 0
