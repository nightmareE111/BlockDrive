# BlockDrive

**Store any file inside a real Minecraft Java world, then recover it.**

BlockDrive is a prototype that maps each data byte to two concrete blocks:
- the first block stores the byte's high 4 bits
- the second block stores the low 4 bits

It uses 16 concrete colors as a 4-bit alphabet. The decoder reads those blocks in the same order, rebuilds the bytes, restores the original filename, and prints a SHA-256 hash.

## Requirements

- Minecraft **Java Edition**
- Python 3.10-3.12 recommended
- Amulet Core

Install:

```bash
python -m pip install amulet-core
```

## Important: use a copy of your world

1. Close Minecraft completely.
2. Find your Java world's save folder (it contains `level.dat`).
3. Copy the entire world folder somewhere safe.
4. Run BlockDrive against the COPY, not your original world.
5. Do not edit, flatten, or otherwise modify the stored concrete-block region before decoding.

This prototype targets Java 1.20.4 block translation through Amulet. It edits the existing world's Overworld. Test on a disposable copy first.

## Store a file

```bash
python blockdrive.py encode --world "C:\Users\YOU\AppData\Roaming\.minecraft\saves\TestWorld" --file "C:\Users\YOU\Desktop\sample.zip" --x 0 --y 80 --z 0
```

The default origin is `(0, 80, 0)`. You can choose another origin with `--x`, `--y`, and `--z`.

## Recover it

Use the same world copy and exactly the same origin:

```bash
python blockdrive.py decode --world "C:\Users\YOU\AppData\Roaming\.minecraft\saves\TestWorld" --out recovered --x 0 --y 80 --z 0
```

The recovered file appears in the `recovered` folder.

## How much space?

Each source byte uses **2 blocks**. Blocks are laid out in a 64 x 64 horizontal pattern, then continue upward in another layer. A 1 MiB file therefore needs a little over 2 million blocks including the header. Large files can take a long time and may create a very large edited area.

## Data format

The byte stream begins with:

| Field | Size |
|---|---:|
| Magic `BLKD` | 4 bytes |
| UTF-8 filename length | 1 byte |
| Payload length (big-endian) | 4 bytes |
| Filename | variable |
| Original file bytes | variable |

The world is the carrier: every nibble is represented by one real Minecraft concrete block. This is not a renamed file, a ZIP appended to another file, or a text/base64 dump.

## Limitations of this prototype

- Java Edition only; Bedrock is not currently targeted.
- Uses an existing world; it does not generate a new world from scratch.
- The stored structure is a dense block column/layer pattern, not a decorative build yet.
- No compression, encryption, redundancy, or error correction.
- If any encoded block is changed, the data may fail to decode.
- Always preserve a clean backup of the encoded world.
- This project is a proof of concept; test with a small file first.

## Project check

After recovery, compare the printed SHA-256 with the original file's hash. Matching hashes prove the recovered bytes are identical.

