"""
ESP32 Bridge Node — reads Open Ephys binary from one ESP32 node and publishes
sensor_msgs/Imu and std_msgs/Float32MultiArray to ROS2 topics.

Channel map (firmware v1.4+):
  ch0–2  accel [m/s^2]  (raw or gravity-removed when FILTER 1)
  ch3–5  gyro  [rad/s]  (raw)
  ch6    DIO
  ch7–10 qw, qx, qy, qz (int16 / 32767 → float)

Usage:
  ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args \
    -p node_id:=master \
    -p host:=192.168.4.1 \
    -p port:=5000

Or via serial bridge:
  python3 host/serial_tcp_bridge.py COM5 --plugin
  ros2 run rehab_robotics_bridge esp32_bridge_node --ros-args -p host:=127.0.0.1
"""
from __future__ import annotations

import asyncio
import struct
import time
from typing import Optional

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Vector3
from sensor_msgs.msg import Imu
from std_msgs.msg import Float32MultiArray, Header

HEADER_STRUCT = struct.Struct('<iiHiii')
HEADER_SIZE = HEADER_STRUCT.size
QUAT_SCALE = 1.0 / 32767.0
ACCEL_SCALE = 1.0 / 100.0   # firmware sends accel * 100 as int16
GYRO_SCALE = 1.0 / 1000.0   # firmware sends gyro * 1000 as int16
NUM_CHANNELS = 11


class Esp32BridgeNode(Node):
    def __init__(self) -> None:
        super().__init__('esp32_bridge_node')

        self.declare_parameter('node_id', 'master')
        self.declare_parameter('host', '127.0.0.1')
        self.declare_parameter('port', 5000)
        self.declare_parameter('reconnect_delay_s', 5.0)

        node_id = self.get_parameter('node_id').value
        self._host: str = self.get_parameter('host').value
        self._port: int = self.get_parameter('port').value
        self._reconnect_delay: float = self.get_parameter('reconnect_delay_s').value

        topic_prefix = f'/esp32/{node_id}'
        self._pub_imu = self.create_publisher(Imu, f'{topic_prefix}/imu', 10)
        self._pub_raw = self.create_publisher(Float32MultiArray, f'{topic_prefix}/raw', 10)

        self.get_logger().info(
            f'ESP32 bridge [{node_id}] → {self._host}:{self._port} | '
            f'topics: {topic_prefix}/imu, {topic_prefix}/raw'
        )

        # Run async reader in background thread via asyncio event loop
        import threading
        self._loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._run_loop, daemon=True)
        t.start()

    def _run_loop(self) -> None:
        self._loop.run_until_complete(self._reconnect_forever())

    async def _reconnect_forever(self) -> None:
        while rclpy.ok():
            try:
                await self._connect_and_read()
            except Exception as exc:
                self.get_logger().warning(
                    f'Connection lost: {exc} — retrying in {self._reconnect_delay} s'
                )
            await asyncio.sleep(self._reconnect_delay)

    async def _connect_and_read(self) -> None:
        reader, writer = await asyncio.open_connection(self._host, self._port)
        self.get_logger().info(f'Connected to {self._host}:{self._port}')

        try:
            # Open Ephys / Plugin handshake
            writer.write(b'REDPITAYA\n')
            await writer.drain()
            line = await asyncio.wait_for(reader.readline(), timeout=5.0)
            self.get_logger().debug(f'handshake: {line.strip()}')

            # Expect SENSORS reply then send START
            line2 = await asyncio.wait_for(reader.readline(), timeout=2.0)
            if line2:
                self.get_logger().debug(f'handshake2: {line2.strip()}')

            writer.write(b'START\n')
            await writer.drain()
            ack = await asyncio.wait_for(reader.readline(), timeout=5.0)
            self.get_logger().info(f'START ack: {ack.strip()}')

            buf = bytearray()
            n_frames = 0

            while rclpy.ok():
                # Read until we have a full header
                while len(buf) < HEADER_SIZE:
                    chunk = await reader.read(4096)
                    if not chunk:
                        raise EOFError('connection closed')
                    buf.extend(chunk)

                _off, num_bytes, _bd, elem, n_ch, _n_per = HEADER_STRUCT.unpack_from(buf, 0)
                if elem != 2:
                    raise ValueError(f'expected int16 payload (elem=2), got {elem}')
                total = HEADER_SIZE + num_bytes

                while len(buf) < total:
                    chunk = await reader.read(4096)
                    if not chunk:
                        raise EOFError('connection closed during payload')
                    buf.extend(chunk)

                # Parse one frame: n_ch × n_per int16 samples, C order
                payload = buf[HEADER_SIZE:total]
                del buf[:total]

                # n_per samples per channel; use only the first sample per publish
                n_per = max(1, num_bytes // (n_ch * 2))
                s16 = [
                    int.from_bytes(payload[i * 2:i * 2 + 2], 'little', signed=True)
                    for i in range(n_ch * n_per)
                ]

                # Channel-first layout: s16[ch * n_per + sample]
                def ch(c: int) -> int:
                    return s16[c * n_per]

                t_now = time.time()

                if n_ch >= NUM_CHANNELS:
                    qw = ch(7) * QUAT_SCALE
                    qx = ch(8) * QUAT_SCALE
                    qy = ch(9) * QUAT_SCALE
                    qz = ch(10) * QUAT_SCALE

                    ax = ch(0) * ACCEL_SCALE
                    ay = ch(1) * ACCEL_SCALE
                    az = ch(2) * ACCEL_SCALE

                    gx = ch(3) * GYRO_SCALE
                    gy = ch(4) * GYRO_SCALE
                    gz = ch(5) * GYRO_SCALE

                    imu_msg = Imu()
                    imu_msg.header = Header()
                    imu_msg.header.stamp = self.get_clock().now().to_msg()
                    imu_msg.header.frame_id = 'esp32'
                    imu_msg.orientation.w = qw
                    imu_msg.orientation.x = qx
                    imu_msg.orientation.y = qy
                    imu_msg.orientation.z = qz
                    imu_msg.linear_acceleration.x = ax
                    imu_msg.linear_acceleration.y = ay
                    imu_msg.linear_acceleration.z = az
                    imu_msg.angular_velocity.x = gx
                    imu_msg.angular_velocity.y = gy
                    imu_msg.angular_velocity.z = gz
                    # Mark covariance as unknown
                    imu_msg.orientation_covariance[0] = -1.0
                    imu_msg.linear_acceleration_covariance[0] = -1.0
                    imu_msg.angular_velocity_covariance[0] = -1.0
                    self._pub_imu.publish(imu_msg)

                # Always publish raw channels
                raw_msg = Float32MultiArray()
                raw_msg.data = [ch(c) / 32767.0 for c in range(n_ch)]
                self._pub_raw.publish(raw_msg)

                n_frames += 1
                if n_frames % 500 == 0:
                    self.get_logger().info(f'published {n_frames} frames')

        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


import contextlib


def main(args=None):
    rclpy.init(args=args)
    node = Esp32BridgeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
