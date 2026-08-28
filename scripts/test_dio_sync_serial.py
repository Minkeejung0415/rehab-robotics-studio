#!/usr/bin/env python3
"""Compare STEP ESP32 DIO transitions over USB without relying on hotspot UDP."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
import statistics
import threading
import time

import serial
from serial import SerialException


STATUS_RE = re.compile(
    r"^DIO_STATUS_OK protocol=dio-sync-v1 role=(master|slave) "
    r"level=([01]) edges=(\d+) edge_time_us=(-?\d+) "
    r"edge_sync_valid=([01]) clock_sync_valid=([01])$"
)
EDGE_RE = re.compile(
    r"^DIO_EDGE protocol=dio-sync-v1 role=(master|slave) "
    r"level=([01]) edges=(\d+) edge_time_us=(-?\d+) edge_sync_valid=([01])$"
)
MONITOR_RE = re.compile(
    r"^DIO_MONITOR_OK protocol=dio-sync-v1 role=(master|slave) enabled=([01])$"
)
FIRMWARE_STATUS_RE = re.compile(r"^STATUS\s+(.*)$")


@dataclass(frozen=True)
class DioEvent:
    role: str
    level: int
    edges: int
    time_us: int


def parse_status(line: str) -> tuple[DioEvent, bool, bool] | None:
    match = STATUS_RE.match(line.strip())
    if match is None:
        return None
    role, level, edges, time_us, edge_valid, clock_valid = match.groups()
    return (
        DioEvent(role, int(level), int(edges), int(time_us)),
        edge_valid == "1",
        clock_valid == "1",
    )


def pair_events(
    master: list[DioEvent], slave: list[DioEvent], max_pair_us: int = 100_000
) -> list[tuple[DioEvent, DioEvent, int]]:
    unused = set(range(len(slave)))
    pairs: list[tuple[DioEvent, DioEvent, int]] = []
    for master_event in master:
        candidates = [
            index
            for index in unused
            if slave[index].level == master_event.level
        ]
        if not candidates:
            continue
        index = min(
            candidates,
            key=lambda candidate: abs(master_event.time_us - slave[candidate].time_us),
        )
        delta_us = master_event.time_us - slave[index].time_us
        if abs(delta_us) <= max_pair_us:
            unused.remove(index)
            pairs.append((master_event, slave[index], delta_us))
    return pairs


class BoardReader(threading.Thread):
    def __init__(
        self,
        port: str,
        expected_role: str,
        sample_rate: int | None = None,
        interval_s: float = 0.05,
    ):
        super().__init__(daemon=True)
        self.port = port
        self.expected_role = expected_role
        self.requested_sample_rate = sample_rate
        self.interval_s = interval_s
        self.events: list[DioEvent] = []
        self.clock_valid = False
        self.monitor_enabled = False
        self.latest: DioEvent | None = None
        self.error: str | None = None
        self.status_history: list[tuple[float, dict[str, int]]] = []
        self._seen: set[tuple[int, int]] = set()
        self._lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._monitor_requested = threading.Event()
        self._status_requested = threading.Event()

    def run(self) -> None:
        try:
            with serial.Serial(self.port, 115200, timeout=0.1) as device:
                device.reset_input_buffer()
                last_command = 0.0
                last_firmware_status = 0.0
                while not self._stop_requested.is_set():
                    now = time.monotonic()
                    if now - last_command >= 0.25:
                        if self.requested_sample_rate is not None:
                            with self._lock:
                                configured_rate = (
                                    self.status_history[-1][1].get("sample_hz")
                                    if self.status_history
                                    else None
                                )
                            if configured_rate != self.requested_sample_rate:
                                device.write(
                                    f"FREQ:{self.requested_sample_rate}\n".encode("ascii")
                                )
                        command = (
                            b"DIO_MONITOR ON\n"
                            if self._monitor_requested.is_set()
                            else b"DIO_STATUS\n"
                        )
                        device.write(command)
                        device.flush()
                        last_command = now
                    with self._lock:
                        configured_rate = (
                            self.status_history[-1][1].get("sample_hz")
                            if self.status_history
                            else None
                        )
                    needs_rate_check = (
                        self.requested_sample_rate is not None
                        and configured_rate != self.requested_sample_rate
                    )
                    if self._status_requested.is_set() or (
                        needs_rate_check and now - last_firmware_status >= 1.0
                    ):
                        device.write(b"STATUS\n")
                        device.flush()
                        self._status_requested.clear()
                        last_firmware_status = now
                    raw = device.readline()
                    if not raw:
                        continue
                    line = raw.decode("utf-8", errors="replace").strip()
                    firmware_status = FIRMWARE_STATUS_RE.match(line)
                    if firmware_status is not None:
                        values: dict[str, int] = {}
                        for token in firmware_status.group(1).split():
                            if "=" not in token:
                                continue
                            key, value = token.split("=", 1)
                            try:
                                values[key] = int(value)
                            except ValueError:
                                continue
                        with self._lock:
                            self.status_history.append((time.monotonic(), values))
                        continue
                    parsed = parse_status(line)
                    if parsed is not None:
                        event, _edge_valid, clock_valid = parsed
                        if event.role != self.expected_role:
                            self.error = (
                                f"{self.port} expected {self.expected_role}, got {event.role}"
                            )
                            return
                        with self._lock:
                            self.latest = event
                            self.clock_valid = clock_valid
                        continue
                    monitor_match = MONITOR_RE.match(line)
                    if monitor_match is not None:
                        role, enabled = monitor_match.groups()
                        if role == self.expected_role:
                            with self._lock:
                                self.monitor_enabled = enabled == "1"
                        continue
                    edge_match = EDGE_RE.match(line)
                    if edge_match is None:
                        continue
                    role, level, edges, time_us, edge_valid = edge_match.groups()
                    if role != self.expected_role or edge_valid != "1":
                        continue
                    event = DioEvent(role, int(level), int(edges), int(time_us))
                    with self._lock:
                        key = (event.edges, event.time_us)
                        if key not in self._seen:
                            self._seen.add(key)
                            self.events.append(event)
                device.write(b"DIO_MONITOR OFF\n")
                device.flush()
        except (SerialException, OSError) as exc:
            self.error = f"{self.port}: {exc}"

    def snapshot(self) -> tuple[DioEvent | None, bool, list[DioEvent]]:
        with self._lock:
            return self.latest, self.clock_valid, list(self.events)

    def firmware_status_snapshot(self) -> list[tuple[float, dict[str, int]]]:
        with self._lock:
            return [(timestamp, dict(values)) for timestamp, values in self.status_history]

    def request_firmware_status(self) -> None:
        self._status_requested.set()

    def enable_monitor(self) -> None:
        self._monitor_requested.set()

    def clear_events(self) -> None:
        with self._lock:
            self.events.clear()

    def stop(self) -> None:
        self._stop_requested.set()


def percentile_nearest(values: list[int], fraction: float) -> int:
    ordered = sorted(values)
    index = round((len(ordered) - 1) * fraction)
    return ordered[index]


def interval_summary(events: list[DioEvent]) -> str:
    if len(events) < 2:
        return "unavailable"
    intervals_ms = [
        (current.time_us - previous.time_us) / 1000
        for previous, current in zip(events, events[1:])
    ]
    return (
        f"median={statistics.median(intervals_ms):.3f}ms "
        f"min={min(intervals_ms):.3f}ms max={max(intervals_ms):.3f}ms"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--master-port", default="COM3")
    parser.add_argument("--slave-port", default="COM4")
    parser.add_argument("--duration", type=float, default=12.0)
    parser.add_argument("--sync-timeout", type=float, default=30.0)
    parser.add_argument("--threshold-ms", type=float, default=20.0)
    parser.add_argument("--min-pairs", type=int, default=4)
    parser.add_argument("--sample-rate", type=int)
    parser.add_argument("--rate-tolerance-percent", type=float, default=2.0)
    parser.add_argument(
        "--verbose-deltas",
        action="store_true",
        help="Print every paired edge delta; disabled by default for long captures.",
    )
    args = parser.parse_args()

    readers = [
        BoardReader(args.master_port, "master", args.sample_rate),
        BoardReader(args.slave_port, "slave", args.sample_rate),
    ]
    for reader in readers:
        reader.start()

    try:
        deadline = time.monotonic() + args.sync_timeout
        while time.monotonic() < deadline:
            if any(reader.error for reader in readers):
                break
            snapshots = [reader.snapshot() for reader in readers]
            rates_ready = args.sample_rate is None or all(
                reader.firmware_status_snapshot()
                and reader.firmware_status_snapshot()[-1][1].get("sample_hz")
                == args.sample_rate
                for reader in readers
            )
            if (
                rates_ready
                and all(latest is not None and valid for latest, valid, _ in snapshots)
            ):
                break
            time.sleep(0.1)
        else:
            print("FAIL setup: timed out waiting for both USB clocks")
            return 2

        if any(reader.error for reader in readers):
            print("FAIL setup: " + "; ".join(filter(None, (r.error for r in readers))))
            return 2

        if args.sample_rate is not None:
            print(f"Verified acquisition rate: {args.sample_rate} Hz on both boards")

        for reader in readers:
            reader.clear_events()
            reader.enable_monitor()
        monitor_deadline = time.monotonic() + 3.0
        while time.monotonic() < monitor_deadline:
            if all(reader.monitor_enabled for reader in readers):
                break
            time.sleep(0.05)
        else:
            print("FAIL setup: DIO monitor acknowledgement timed out")
            return 2
        for reader in readers:
            reader.clear_events()
        baseline_lengths = [
            len(reader.firmware_status_snapshot()) for reader in readers
        ]
        for reader in readers:
            reader.request_firmware_status()
        status_deadline = time.monotonic() + 3.0
        while time.monotonic() < status_deadline:
            if all(
                len(reader.firmware_status_snapshot()) > baseline_length
                for reader, baseline_length in zip(readers, baseline_lengths)
            ):
                break
            time.sleep(0.01)
        else:
            print("FAIL setup: initial firmware status timed out")
            return 2
        initial_statuses = [
            reader.firmware_status_snapshot()[-1][1] for reader in readers
        ]
        print(
            f"Capturing {args.duration:.1f}s from {args.master_port} master and "
            f"{args.slave_port} slave...",
            flush=True,
        )
        time.sleep(args.duration)
        final_lengths = [len(reader.firmware_status_snapshot()) for reader in readers]
        for reader in readers:
            reader.request_firmware_status()
        status_deadline = time.monotonic() + 3.0
        while time.monotonic() < status_deadline:
            if all(
                len(reader.firmware_status_snapshot()) > final_length
                for reader, final_length in zip(readers, final_lengths)
            ):
                break
            time.sleep(0.01)
        else:
            print("FAIL setup: final firmware status timed out")
            return 2
        final_statuses = [
            reader.firmware_status_snapshot()[-1][1] for reader in readers
        ]
        master_events = readers[0].snapshot()[2]
        slave_events = readers[1].snapshot()[2]
    finally:
        for reader in readers:
            reader.stop()
        for reader in readers:
            reader.join(timeout=2)

    pairs = pair_events(master_events, slave_events)
    rate_failures: list[str] = []
    if args.sample_rate is not None:
        for reader, start_values, end_values in zip(
            readers, initial_statuses, final_statuses
        ):
            if "generated" not in start_values or "generated" not in end_values:
                rate_failures.append(f"{reader.expected_role}: missing generated count")
                continue
            measured_rate = (
                end_values["generated"] - start_values["generated"]
            ) / args.duration
            error_percent = abs(measured_rate - args.sample_rate) / args.sample_rate * 100
            print(
                f"{reader.expected_role.capitalize()} acquisition: "
                f"{measured_rate:.2f} samples/s, "
                f"generated={end_values['generated'] - start_values['generated']}, "
                f"loop_overruns={end_values.get('loop_overruns', -1)}, "
                f"queue_drops={end_values.get('queue_drops', -1)}"
            )
            if error_percent > args.rate_tolerance_percent:
                rate_failures.append(
                    f"{reader.expected_role}: rate error {error_percent:.2f}%"
                )
    print(
        f"Transitions: master={len(master_events)} slave={len(slave_events)} "
        f"paired={len(pairs)}"
    )
    print(f"Master intervals: {interval_summary(master_events)}")
    print(f"Slave intervals: {interval_summary(slave_events)}")
    if len(pairs) < args.min_pairs:
        print(f"FAIL insufficient paired transitions (need {args.min_pairs})")
        return 1
    if rate_failures:
        print("FAIL acquisition: " + "; ".join(rate_failures))
        return 1

    deltas = [delta for _, _, delta in pairs]
    absolute = [abs(delta) for delta in deltas]
    max_abs = max(absolute)
    threshold_us = round(args.threshold_ms * 1000)
    print(
        "Skew: "
        f"mean={statistics.fmean(deltas) / 1000:.3f}ms "
        f"mean_abs={statistics.fmean(absolute) / 1000:.3f}ms "
        f"p95_abs={percentile_nearest(absolute, 0.95) / 1000:.3f}ms "
        f"max_abs={max_abs / 1000:.3f}ms"
    )
    if args.verbose_deltas:
        print("Deltas_ms: " + ", ".join(f"{delta / 1000:.3f}" for delta in deltas))
    if max_abs > threshold_us:
        print(f"FAIL max skew exceeds {args.threshold_ms:.3f}ms")
        return 1
    print(f"PASS max skew is within {args.threshold_ms:.3f}ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
