#!/usr/bin/env python3
"""Continuously drain an ESP32 USB CDC port so firmware logging cannot block."""

from __future__ import annotations

import argparse
import sys
import time

import serial
from serial import SerialException


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("port")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()

    while True:
        try:
            with serial.Serial(args.port, args.baud, timeout=0.25) as device:
                print(f"[serial-drain] opened {args.port} at {args.baud}", flush=True)
                while True:
                    data = device.readline()
                    if data:
                        sys.stdout.buffer.write(data)
                        sys.stdout.buffer.flush()
        except (SerialException, OSError) as exc:
            print(f"[serial-drain] {args.port}: {exc}; retrying", file=sys.stderr, flush=True)
            time.sleep(1.0)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    raise SystemExit(main())
