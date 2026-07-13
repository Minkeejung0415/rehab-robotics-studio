"""
IMU Aggregator Node — reads nodes.yaml and spawns one Esp32BridgeNode per entry.

config/nodes.yaml format:
  nodes:
    - id: master
      host: 192.168.4.1
      port: 5000
    - id: slave_1
      host: 192.168.4.2
      port: 5000

Usage:
  ros2 run rehab_robotics_bridge imu_aggregator_node
"""
from __future__ import annotations

import threading

import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node

from .esp32_bridge_node import Esp32BridgeNode


class ImuAggregatorNode(Node):
    def __init__(self) -> None:
        super().__init__('imu_aggregator_node')
        self.declare_parameter('config_file', '')

        config_path = self.get_parameter('config_file').value
        if not config_path:
            import os
            import ament_index_python.packages as ament
            pkg_share = ament.get_package_share_directory('rehab_robotics_bridge')
            config_path = os.path.join(pkg_share, 'config', 'nodes.yaml')

        self.get_logger().info(f'Loading node config from {config_path}')
        self._bridge_nodes: list[Esp32BridgeNode] = []
        self._load_and_spawn(config_path)

    def _load_and_spawn(self, config_path: str) -> None:
        import yaml
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
        except FileNotFoundError:
            self.get_logger().error(f'Config not found: {config_path}')
            return

        for entry in cfg.get('nodes', []):
            node_id = entry.get('id', 'unknown')
            host = entry.get('host', '127.0.0.1')
            port = int(entry.get('port', 5000))
            self.get_logger().info(f'Spawning bridge for node [{node_id}] at {host}:{port}')

            # Create a bridge node inline; rclpy will manage it
            bridge = Esp32BridgeNode.__new__(Esp32BridgeNode)
            rclpy.node.Node.__init__(bridge, f'esp32_bridge_{node_id}')
            # Override parameters directly
            bridge._host = host
            bridge._port = port
            bridge._reconnect_delay = 5.0

            from sensor_msgs.msg import Imu
            from std_msgs.msg import Float32MultiArray
            topic_prefix = f'/esp32/{node_id}'
            bridge._pub_imu = bridge.create_publisher(Imu, f'{topic_prefix}/imu', 10)
            bridge._pub_raw = bridge.create_publisher(Float32MultiArray, f'{topic_prefix}/raw', 10)

            import asyncio
            bridge._loop = asyncio.new_event_loop()
            t = threading.Thread(target=bridge._run_loop, daemon=True)
            t.start()

            self._bridge_nodes.append(bridge)


def main(args=None):
    rclpy.init(args=args)
    node = ImuAggregatorNode()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    for bn in node._bridge_nodes:
        executor.add_node(bn)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()
