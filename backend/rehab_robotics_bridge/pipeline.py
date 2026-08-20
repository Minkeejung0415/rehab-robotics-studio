"""Plugin-compatible JSON processing primitives for the ESP32 ROS 2 pipeline."""
from __future__ import annotations

import json
import pathlib
import re
import socket
import time
from collections import deque
from typing import Any

RAW_SCHEMA = 'oe_esp32.raw.v1'
_IMU_KEYS = ('ax', 'ay', 'az', 'gx', 'gy', 'gz', 'mx', 'my', 'mz')
_QUAT_KEYS = ('qw', 'qx', 'qy', 'qz')


def decode_raw(payload: str) -> dict[str, Any]:
    sample = json.loads(payload)
    if sample.get('topic_schema') != RAW_SCHEMA:
        raise ValueError('unsupported ESP payload schema')
    if not isinstance(sample.get('imu'), dict) or not isinstance(sample.get('quat'), dict):
        raise ValueError('payload is missing imu or quat fields')
    for key in (*_IMU_KEYS, *_QUAT_KEYS):
        group = sample['imu'] if key in _IMU_KEYS else sample['quat']
        if not isinstance(group.get(key), int):
            raise ValueError(f'payload field {key} must be an integer')
    return sample


class SampleFilter:
    """Moving-average filter that preserves the plugin raw JSON envelope."""

    def __init__(self, window: int = 1) -> None:
        self._window = max(1, int(window))
        self._history: dict[str, deque[int]] = {
            key: deque(maxlen=self._window) for key in (*_IMU_KEYS, *_QUAT_KEYS)
        }

    def filter_json(self, payload: str) -> str:
        sample = decode_raw(payload)
        for key in _IMU_KEYS:
            values = self._history[key]
            values.append(sample['imu'][key])
            sample['imu'][key] = round(sum(values) / len(values))
        for key in _QUAT_KEYS:
            values = self._history[key]
            values.append(sample['quat'][key])
            sample['quat'][key] = round(sum(values) / len(values))
        sample['topic_schema'] = 'oe_esp32.filtered.v1'
        return json.dumps(sample, sort_keys=True, separators=(',', ':'))


def opensim_packet(payload: str) -> bytes:
    sample = json.loads(payload)
    if sample.get('topic_schema') not in (RAW_SCHEMA, 'oe_esp32.filtered.v1'):
        raise ValueError('unsupported OpenSim payload schema')
    return json.dumps(sample, sort_keys=True, separators=(',', ':')).encode('utf-8')


def send_opensim_packet(payload: str, host: str, port: int) -> None:
    data = opensim_packet(payload)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.sendto(data, (host, int(port)))


def safe_session_path(output_dir: str, session_prefix: str, topic: str) -> pathlib.Path:
    safe_prefix = re.sub(r'[^A-Za-z0-9_.-]+', '_', session_prefix).strip('._') or 'ros2_raw'
    role = re.sub(r'[^A-Za-z0-9_.-]+', '_', topic.strip('/').split('/')[-1]) or 'unknown'
    directory = pathlib.Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f'{safe_prefix}_{role}_{time.strftime("%Y%m%d_%H%M%S")}.jsonl'
