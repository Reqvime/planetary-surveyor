"""Read-only inspection of discovery records in a compressed NMS save.

This script never writes to the save directory.  It decodes the game's chunked
LZ4 container in memory and prints compact JSON paths/records around a requested
timestamp or universe address.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct
from typing import Any, Iterator

import lz4.block


MAGIC = 0xFEEDA1E5
DISCOVERY_KEYS = {"fDu", "DiscoveryManagerData", "ETO", "DiscoveryData-v1"}


def decode_save(path: Path) -> Any:
    data = path.read_bytes()
    cursor = 0
    chunks: list[bytes] = []
    while cursor + 16 <= len(data):
        magic, compressed_size, uncompressed_size, _unknown = struct.unpack_from(
            "<IIII", data, cursor
        )
        if magic != MAGIC:
            break
        cursor += 16
        end = cursor + compressed_size
        if end > len(data):
            raise ValueError(f"truncated chunk at offset {cursor - 16}")
        chunks.append(
            lz4.block.decompress(
                data[cursor:end], uncompressed_size=uncompressed_size
            )
        )
        cursor = end

    raw = b"".join(chunks).replace(b"\x00", b"")
    last_good = max(raw.rfind(b"}"), raw.rfind(b"]"))
    if last_good < 0:
        raise ValueError("decoded data contains no JSON terminator")
    return json.loads(raw[: last_good + 1].decode("utf-8"))


def walk(value: Any, path: str = "$") -> Iterator[tuple[str, Any]]:
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, f"{path}[{index}]")


def contains_scalar(value: Any, needle: str) -> bool:
    if isinstance(value, dict):
        return any(contains_scalar(child, needle) for child in value.values())
    if isinstance(value, list):
        return any(contains_scalar(child, needle) for child in value)
    return str(value) == needle


def compact(value: Any, limit: int = 4000) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("save", type=Path)
    parser.add_argument("--timestamp")
    parser.add_argument("--ua")
    parser.add_argument(
        "--dump-containers",
        action="store_true",
        help="print full discovery containers (very verbose)",
    )
    args = parser.parse_args()

    root = decode_save(args.save)
    print(f"decoded_root={type(root).__name__}")

    if args.dump_containers:
        for path, value in walk(root):
            if isinstance(value, dict):
                for key in value:
                    if key in DISCOVERY_KEYS:
                        print(
                            f"discovery_container={path}.{key} "
                            f"{compact(value[key], 12000)}"
                        )

    manager = root.get("fDu", root.get("DiscoveryManagerData", {}))
    discovery_data = manager.get("ETO", manager.get("DiscoveryData-v1", {}))
    store = discovery_data.get("OsQ", discovery_data.get("Store", {}))
    records = store.get("?fB", store.get("Record", []))
    if args.ua:
        selected = []
        for record in records:
            data = record.get("8P3", record.get("DD", {}))
            if str(data.get("5L6", data.get("UA"))) == args.ua:
                selected.append(record)
        print(f"ua_records={len(selected)}")
        by_type: dict[str, list[dict[str, Any]]] = {}
        for record in selected:
            data = record.get("8P3", record.get("DD", {}))
            owner = record.get("ksu", record.get("OWS", {}))
            kind = str(data.get("<Dn", data.get("DT")))
            keys = data.get("bEr", data.get("VP", []))
            timestamp = owner.get("3I1", owner.get("TS"))
            by_type.setdefault(kind, []).append(
                {"timestamp": timestamp, "keys": keys}
            )
        for kind, items in sorted(by_type.items()):
            key_tuples = [tuple(map(str, item["keys"])) for item in items]
            print(
                f"ua_type={kind} records={len(items)} "
                f"unique_keys={len(set(key_tuples))}"
            )
            for item in sorted(items, key=lambda entry: entry["timestamp"] or 0):
                print(
                    f"ua_record type={kind} timestamp={item['timestamp']} "
                    f"keys={item['keys']}"
                )

    needles = [needle for needle in (args.timestamp, args.ua) if needle]
    for needle in needles:
        print(f"needle={needle}")
        matches = 0
        for path, value in walk(root):
            if isinstance(value, dict) and contains_scalar(value, needle):
                print(f"match={path} {compact(value)}")
                matches += 1
                if matches >= 50:
                    print("match_limit=50")
                    break
        print(f"matches={matches}")


if __name__ == "__main__":
    main()
