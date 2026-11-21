
#!/usr/bin/env python3
"""BlockDrive: Store and recover files using Minecraft concrete blocks."""

from __future__ import annotations

import argparse
import hashlib
import struct
import sys
from pathlib import Path

import amulet
from amulet.api.block import Block

MAGIC = b"BLKD"
GAME_VERSION = ("java", (1, 20, 4))
DIMENSION = "minecraft:overworld"
WIDTH = 64
DEPTH = 64

PALETTE = [
    "white", "orange", "magenta", "light_blue",
    "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue",
    "brown", "green", "red", "black",
]

# Map each concrete block name to its nibble value.
PALETTE_LOOKUP = {
    f"{color}_concrete": index
    for index, color in enumerate(PALETTE)
}


def pack_file(path: Path) -> bytes:
    payload = path.read_bytes()
    name = path.name.encode("utf-8")

    if len(name) > 255:
        raise ValueError("Filename is too long (maximum 255 UTF-8 bytes).")

    if len(payload) > 0xFFFFFFFF:
        raise ValueError("Maximum supported file size is 4 GiB.")

    return MAGIC + struct.pack(">BI", len(name), len(payload)) + name + payload


def unpack_blob(blob: bytes) -> tuple[str, bytes]:
    if len(blob) < 9 or blob[:4] != MAGIC:
        raise ValueError("No BlockDrive header found. Check the world and origin.")

    name_len, data_len = struct.unpack(">BI", blob[4:9])

    end_name = 9 + name_len
    end_data = end_name + data_len

    if len(blob) < end_data:
        raise ValueError("Stored data is incomplete.")

    name = blob[9:end_name].decode("utf-8")
    return name, blob[end_name:end_data]


def position(
    index: int,
    origin: tuple[int, int, int]
) -> tuple[int, int, int]:
    ox, oy, oz = origin

    x = index % WIDTH
    z = (index // WIDTH) % DEPTH
    y = index // (WIDTH * DEPTH)

    return ox + x, oy + y, oz + z


def bytes_to_nibbles(data: bytes) -> list[int]:
    result = []

    for byte in data:
        result.append(byte >> 4)
        result.append(byte & 0x0F)

    return result


def nibbles_to_bytes(values: list[int]) -> bytes:
    if len(values) % 2:
        raise ValueError("Invalid nibble count.")

    return bytes(
        (values[i] << 4) | values[i + 1]
        for i in range(0, len(values), 2)
    )


def read_nibbles(level, count: int, origin: tuple[int, int, int]) -> list[int]:
    values = []

    for i in range(count):
        x, y, z = position(i, origin)

        block, _ = level.get_version_block(
            x, y, z, DIMENSION, GAME_VERSION
        )

        if not isinstance(block, Block):
            raise ValueError(f"Unexpected object at block index {i}.")

        block_name = block.base_name

        if block_name not in PALETTE_LOOKUP:
            raise ValueError(
                f"Unexpected block at index {i}: "
                f"{block.namespaced_name}. "
                "The stored structure may have been changed."
            )

        values.append(PALETTE_LOOKUP[block_name])

    return values


def encode(
    world_path: Path,
    file_path: Path,
    origin: tuple[int, int, int]
) -> None:

    blob = pack_file(file_path)
    nibbles = bytes_to_nibbles(blob)

    print(f"Loading world: {world_path}")
    level = amulet.load_level(str(world_path))

    try:
        for i, nibble in enumerate(nibbles):
            x, y, z = position(i, origin)

            # IMPORTANT: Use valid Minecraft concrete block IDs.
            block_name = f"{PALETTE[nibble]}_concrete"

            level.set_version_block(
                x, y, z,
                DIMENSION,
                GAME_VERSION,
                Block("minecraft", block_name)
            )

            if (i + 1) % 2000 == 0:
                print(
                    f"\rWriting blocks: {i + 1:,}/{len(nibbles):,}",
                    end="",
                    flush=True
                )

        level.save()

    finally:
        level.close()

    print("\nWorld saved. Verifying stored data...")

    # Reopen the world and verify every written block.
    check_level = amulet.load_level(str(world_path))

    try:
        recovered_nibbles = read_nibbles(
            check_level, len(nibbles), origin
        )
    finally:
        check_level.close()

    if recovered_nibbles != nibbles:
        raise ValueError(
            "Verification failed: stored blocks do not match original data."
        )

    print("Verification successful!")

    payload = file_path.read_bytes()

    print(f"Stored {len(blob):,} bytes.")
    print(f"Concrete blocks: {len(nibbles):,}")
    print(f"SHA-256: {hashlib.sha256(payload).hexdigest()}")
    print("Done!")


def decode(
    world_path: Path,
    output_dir: Path,
    origin: tuple[int, int, int]
) -> None:

    print(f"Loading world: {world_path}")
    level = amulet.load_level(str(world_path))

    try:
        # Read the first 9 bytes of the BlockDrive header.
        header_nibbles = read_nibbles(level, 18, origin)
        header = nibbles_to_bytes(header_nibbles)

        if header[:4] != MAGIC:
            raise ValueError("No BlockDrive data at this origin.")

        name_len, data_len = struct.unpack(">BI", header[4:9])

        total_bytes = 9 + name_len + data_len

        if total_bytes > 0xFFFFFFFF + 264:
            raise ValueError("Invalid stored data length.")

        all_nibbles = read_nibbles(
            level, total_bytes * 2, origin
        )

        blob = nibbles_to_bytes(all_nibbles)
        filename, payload = unpack_blob(blob)

    finally:
        level.close()

    output_dir.mkdir(parents=True, exist_ok=True)

    safe_name = Path(filename).name

    if not safe_name or safe_name in (".", ".."):
        raise ValueError("Invalid recovered filename.")

    destination = output_dir / safe_name
    destination.write_bytes(payload)

    print(f"Recovered: {destination}")
    print(f"Bytes: {len(payload):,}")
    print(f"SHA-256: {hashlib.sha256(payload).hexdigest()}")


def parse_origin(args) -> tuple[int, int, int]:
    return args.x, args.y, args.z


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Store and recover files inside Minecraft Java worlds."
    )

    sub = parser.add_subparsers(dest="command", required=True)

    enc = sub.add_parser("encode", help="Store a file.")
    enc.add_argument("--world", required=True, type=Path)
    enc.add_argument("--file", required=True, type=Path)
    enc.add_argument("--x", type=int, default=0)
    enc.add_argument("--y", type=int, default=80)
    enc.add_argument("--z", type=int, default=0)

    dec = sub.add_parser("decode", help="Recover a file.")
    dec.add_argument("--world", required=True, type=Path)
    dec.add_argument("--out", type=Path, default=Path("recovered"))
    dec.add_argument("--x", type=int, default=0)
    dec.add_argument("--y", type=int, default=80)
    dec.add_argument("--z", type=int, default=0)

    args = parser.parse_args()

    if not args.world.exists():
        parser.error(f"World folder does not exist: {args.world}")

    if not (args.world / "level.dat").exists():
        parser.error("Invalid Minecraft world: level.dat missing.")

    try:
        if args.command == "encode":
            if not args.file.is_file():
                parser.error(f"Input file not found: {args.file}")

            encode(args.world, args.file, parse_origin(args))

        else:
            decode(args.world, args.out, parse_origin(args))

    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
