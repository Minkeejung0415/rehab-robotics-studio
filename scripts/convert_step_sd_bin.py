#!/usr/bin/env python3
"""Convert STEP ESP32 STP1-v2 SD binary logs to Excel-ready CSV files.

Examples:
  python scripts/convert_step_sd_bin.py D:\\step_20260825_111650.bin
  python scripts/convert_step_sd_bin.py --watch D:\\recordings
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import struct
import time


MAGIC = 0x31505453  # b"STP1" in little-endian form
VERSION = 2
HEADER_FORMAT = "<IHHHHqHHqqqBBH"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)
CHANNEL_NAMES = (
    "ax", "ay", "az", "gx", "gy", "gz", "mx", "my", "mz",
    "qw_q15", "qx_q15", "qy_q15", "qz_q15", "dio_packed",
)


def read_header(source: Path) -> dict[str, int]:
    with source.open("rb") as handle:
        raw = handle.read(HEADER_SIZE)
    if len(raw) != HEADER_SIZE:
        raise ValueError(f"{source.name}: file is shorter than the {HEADER_SIZE}-byte STP1 header")
    (
        magic, version, record_size, sample_hz, channel_count, start_time_us,
        header_size, flags, scheduled_start_time_us, scheduled_stop_time_us,
        clock_offset_us, node_role, sync_valid, reserved,
    ) = struct.unpack(HEADER_FORMAT, raw)
    if magic != MAGIC:
        raise ValueError(f"{source.name}: not an STP1 log (magic={magic:#010x})")
    if version != VERSION:
        raise ValueError(f"{source.name}: unsupported STP1 version {version}; expected {VERSION}")
    if header_size != HEADER_SIZE:
        raise ValueError(f"{source.name}: header reports {header_size} bytes; expected {HEADER_SIZE}")
    expected_record_size = 16 + channel_count * 2
    if channel_count < 1 or record_size != expected_record_size:
        raise ValueError(
            f"{source.name}: invalid record layout (channels={channel_count}, record_size={record_size})"
        )
    if channel_count != len(CHANNEL_NAMES):
        raise ValueError(f"{source.name}: expected {len(CHANNEL_NAMES)} channels, found {channel_count}")
    return {
        "version": version, "record_size": record_size, "sample_hz": sample_hz,
        "channel_count": channel_count, "start_time_us": start_time_us,
        "header_size": header_size, "flags": flags,
        "scheduled_start_time_us": scheduled_start_time_us,
        "scheduled_stop_time_us": scheduled_stop_time_us,
        "clock_offset_us": clock_offset_us, "node_role": node_role,
        "sync_valid": sync_valid, "reserved": reserved,
    }


def output_paths(source: Path) -> tuple[Path, Path]:
    return source.with_suffix(".csv"), source.with_suffix(".metadata.json")


def convert(source: Path, *, overwrite: bool = False) -> tuple[Path, int]:
    source = source.resolve()
    header = read_header(source)
    csv_path, metadata_path = output_paths(source)
    if csv_path.exists() and not overwrite and csv_path.stat().st_mtime_ns >= source.stat().st_mtime_ns:
        return csv_path, 0

    remainder = (source.stat().st_size - header["header_size"]) % header["record_size"]
    if remainder:
        raise ValueError(f"{source.name}: truncated log; {remainder} trailing byte(s) do not form a record")

    record_format = f"<IIq{header['channel_count']}h"
    if struct.calcsize(record_format) != header["record_size"]:
        raise ValueError(f"{source.name}: record format does not match its declared size")
    temporary_csv = csv_path.with_suffix(".csv.tmp")
    temporary_metadata = metadata_path.with_suffix(".json.tmp")
    row_count = 0
    with source.open("rb") as binary, temporary_csv.open("w", newline="", encoding="utf-8-sig") as text:
        binary.seek(header["header_size"])
        writer = csv.writer(text)
        writer.writerow(("seq", "sample_index", "time_us", "elapsed_s", *CHANNEL_NAMES))
        while raw := binary.read(header["record_size"]):
            if len(raw) != header["record_size"]:
                raise ValueError(f"{source.name}: truncated record at row {row_count + 1}")
            seq, sample_index, time_us, *channels = struct.unpack(record_format, raw)
            writer.writerow((seq, sample_index, time_us, f"{(time_us - header['start_time_us']) / 1_000_000:.6f}", *channels))
            row_count += 1
    metadata = {
        "source_file": source.name,
        "csv_file": csv_path.name,
        "format": "STEP ESP32 STP1 v2",
        "rows": row_count,
        "channels": list(CHANNEL_NAMES),
        **header,
    }
    temporary_metadata.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    temporary_csv.replace(csv_path)
    temporary_metadata.replace(metadata_path)
    return csv_path, row_count


def watch(folder: Path, interval_s: float) -> None:
    folder = folder.resolve()
    print(f"Watching {folder} for completed STEP .bin logs. Press Ctrl+C to stop.")
    completed: dict[Path, tuple[int, int]] = {}
    pending: dict[Path, tuple[tuple[int, int], float]] = {}
    while True:
        for source in folder.glob("*.bin"):
            fingerprint = (source.stat().st_size, source.stat().st_mtime_ns)
            if completed.get(source) == fingerprint:
                continue
            # A file must remain unchanged for one full polling interval before conversion.
            previous = pending.get(source)
            if previous is None or previous[0] != fingerprint:
                pending[source] = (fingerprint, time.monotonic())
                continue
            if time.monotonic() - previous[1] < interval_s:
                continue
            try:
                csv_path, rows = convert(source)
                print(f"Converted {source.name} -> {csv_path.name} ({rows:,} rows)")
            except ValueError as error:
                print(f"Waiting: {error}")
            else:
                completed[source] = fingerprint
                pending.pop(source, None)
        time.sleep(interval_s)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, nargs="?", help="one STP1 .bin file to convert")
    parser.add_argument("--watch", type=Path, metavar="FOLDER", help="continuously convert completed .bin files in this folder")
    parser.add_argument("--interval", type=float, default=2.0, help="watch polling interval in seconds (default: 2)")
    parser.add_argument("--overwrite", action="store_true", help="rebuild an existing CSV")
    args = parser.parse_args()
    if bool(args.file) == bool(args.watch):
        parser.error("provide exactly one file or --watch FOLDER")
    if args.watch:
        if not args.watch.is_dir():
            parser.error(f"watch folder does not exist: {args.watch}")
        watch(args.watch, args.interval)
        return
    if not args.file.is_file():
        parser.error(f"file does not exist: {args.file}")
    csv_path, rows = convert(args.file, overwrite=args.overwrite)
    print(f"Converted {args.file.name} -> {csv_path} ({rows:,} rows)")


if __name__ == "__main__":
    main()
