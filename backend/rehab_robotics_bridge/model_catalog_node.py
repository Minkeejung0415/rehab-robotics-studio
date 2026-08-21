"""ModelCatalogNode: ROS 2 node that publishes the OpenSim model catalog.

Reads the ``opensim_model_path`` ROS parameter, computes a SHA-256 identity
hash of the raw file bytes, enumerates compatible non-Ground PhysicalFrames,
and publishes the result as JSON on ``/rehab/model/catalog``.

Design contracts:
- D-01: SHA-256 of raw bytes; no filename-based identity.
- D-02: Publishes whenever model path changes; empty catalog on missing path.
- D-03: Read-only enumeration; no OpenSim setters, no system init, no visualizer.
- MODEL-03: Fail-closed — missing/ambiguous frames are excluded; no fuzzy match.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import time
from pathlib import Path
from typing import Any

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String

CATALOG_TOPIC = "/rehab/model/catalog"
CATALOG_SCHEMA = "rehab.model_catalog.1"

_TIMER_PERIOD_S = 1.0


def compute_model_hash(model_path: str) -> str:
    """Return the SHA-256 hex digest of raw file bytes at ``model_path``.

    Raises:
        FileNotFoundError: if ``model_path`` does not exist or is not a file.
    """
    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {model_path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def enumerate_compatible_frames(
    model_path: str,
    opensim_module: Any,
) -> list[dict[str, str]]:
    """Enumerate non-Ground compatible frames from the OpenSim model.

    Performs read-only enumeration: no setters called, no system initialization, no
    visualizer fork. Returns a list of ``{segment, frame}`` dicts sorted by
    segment then frame name for deterministic output.

    Compatible frames:
    1. Non-Ground Body objects from ``getBodySet()``.
    2. PhysicalOffsetFrame objects from ``getComponentsList()`` whose parent
       body is a non-Ground Body (best-effort; silently skipped if the API
       is unavailable in the installed bindings).

    Args:
        model_path: Absolute path to the ``.osim`` file.
        opensim_module: The already-imported ``opensim`` Python module.

    Returns:
        Sorted list of ``{segment: str, frame: str}`` dicts.

    Raises:
        ValueError: if the model fails to load (message contains reason).
        FileNotFoundError: if ``model_path`` does not exist.
    """
    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Model file not found: {model_path}")

    try:
        model = opensim_module.Model(str(path))
    except Exception as exc:
        raise ValueError(f"opensim_model_load_failed: {exc}") from exc

    results: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    # Pass 1: iterate BodySet for non-Ground Body objects.
    try:
        body_set = model.getBodySet()
        body_set_size = body_set.getSize()
        body_names: set[str] = set()
        for i in range(body_set_size):
            body = body_set.get(i)
            name = body.getName()
            if name.lower() == "ground":
                continue
            body_names.add(name)
            key = (name, name)
            if key not in seen:
                seen.add(key)
                results.append({"segment": name, "frame": name})
    except Exception:
        # If getBodySet is unavailable, skip silently.
        body_names = set()

    # Pass 2: look for PhysicalOffsetFrame components attached to a non-Ground Body.
    # Use getComponentsList() if available; fall back gracefully if not.
    try:
        components_iter = model.getComponentsList()
        for comp in components_iter:
            class_name = ""
            try:
                class_name = comp.getConcreteClassName()
            except Exception:
                try:
                    class_name = type(comp).__name__
                except Exception:
                    pass

            if "PhysicalOffsetFrame" not in class_name:
                continue

            frame_name = ""
            parent_name = ""
            try:
                frame_name = comp.getName()
                # Try to find the parent Body name via getParentFrame or socket.
                parent_frame = None
                get_parent = getattr(comp, "getParentFrame", None)
                if callable(get_parent):
                    parent_frame = get_parent()
                else:
                    # Try socket-based access (older bindings).
                    get_socket = getattr(comp, "getSocket", None)
                    if callable(get_socket):
                        try:
                            socket_obj = get_socket("parent")
                            parent_frame = socket_obj.getConnecteeAsObject()
                        except Exception:
                            parent_frame = None

                if parent_frame is not None:
                    parent_name = parent_frame.getName()
            except Exception:
                continue

            if not frame_name or not parent_name:
                continue
            if parent_name.lower() == "ground":
                continue
            # Only include if parent is a known Body (non-Ground).
            if parent_name not in body_names and body_names:
                continue

            key = (parent_name, frame_name)
            if key not in seen:
                seen.add(key)
                results.append({"segment": parent_name, "frame": frame_name})
    except Exception:
        # getComponentsList unavailable or iteration failed — body-only results suffice.
        pass

    results.sort(key=lambda d: (d["segment"], d["frame"]))
    return results


class ModelCatalogNode(Node):
    """Publish the OpenSim model catalog on ``/rehab/model/catalog``.

    On startup and on each timer tick, reads ``opensim_model_path`` and
    publishes a JSON catalog if the path has changed. The catalog includes
    the SHA-256 hash of the raw file, the enumerated compatible frames, and
    an ``error_reason`` string on any failure.
    """

    def __init__(self) -> None:
        super().__init__("model_catalog")

        parameter_defaults = {
            "opensim_model_path": "",
        }
        values = {
            name: self.declare_parameter(name, default).value
            for name, default in parameter_defaults.items()
        }
        del values  # Parameters declared; read dynamically via get_parameter.

        self._catalog_publisher = self.create_publisher(
            String,
            CATALOG_TOPIC,
            QoSProfile(
                depth=1,
                durability=DurabilityPolicy.TRANSIENT_LOCAL,
                reliability=ReliabilityPolicy.RELIABLE,
            ),
        )

        self._last_model_path: str = ""
        self._timer = self.create_timer(_TIMER_PERIOD_S, self._on_catalog_timer)
        # Publish immediately on startup for a fast first announcement.
        self._on_catalog_timer()

    def _on_catalog_timer(self) -> None:
        """Check if model path changed; publish catalog if so."""
        try:
            new_path = str(
                self.get_parameter("opensim_model_path").value or ""
            )
        except Exception:
            new_path = ""

        if new_path == self._last_model_path:
            return

        self._build_and_publish_catalog(new_path)

    def _build_and_publish_catalog(self, model_path: str) -> None:
        """Build catalog JSON for ``model_path`` and publish it."""

        # Always update the tracked path so the timer does not retry every tick
        # on a broken path (re-attempt only when the operator changes the param).
        self._last_model_path = model_path

        catalog: dict[str, Any] = {
            "schema_version": CATALOG_SCHEMA,
            "model_hash": "",
            "model_path": model_path,
            "frame_list": [],
            "error_reason": "",
        }

        if not model_path:
            catalog["error_reason"] = "no_model_path"
            self._publish_catalog(catalog)
            return

        if not Path(model_path).is_file():
            catalog["error_reason"] = "model_path_not_found"
            self._publish_catalog(catalog)
            self.get_logger().warning(
                f"ModelCatalogNode: model file not found: {model_path}"
            )
            return

        # Compute SHA-256 hash.
        try:
            model_hash = compute_model_hash(model_path)
        except Exception as exc:
            catalog["error_reason"] = f"hash_failed:{str(exc)[:200]}"
            self._publish_catalog(catalog)
            self.get_logger().error(
                f"ModelCatalogNode: hash failed for {model_path}: {exc}"
            )
            return

        catalog["model_hash"] = model_hash

        # Lazy-import opensim.
        try:
            opensim_module = importlib.import_module("opensim")
        except (ImportError, ModuleNotFoundError):
            catalog["error_reason"] = "opensim_bindings_unavailable"
            self._publish_catalog(catalog)
            self.get_logger().warning(
                "ModelCatalogNode: opensim bindings unavailable; "
                "publishing catalog with hash but no frame_list"
            )
            return

        # Enumerate compatible frames.
        try:
            frame_list = enumerate_compatible_frames(model_path, opensim_module)
            catalog["frame_list"] = frame_list
            catalog["error_reason"] = ""
            self.get_logger().info(
                f"ModelCatalogNode: catalog ready — "
                f"{len(frame_list)} frames, hash={model_hash[:12]}..."
            )
        except Exception as exc:
            reason = str(exc)[:200]
            catalog["error_reason"] = reason
            catalog["frame_list"] = []
            self.get_logger().error(
                f"ModelCatalogNode: frame enumeration failed: {exc}"
            )

        self._publish_catalog(catalog)

    def _publish_catalog(self, catalog: dict[str, Any]) -> None:
        """Serialize and publish the catalog dict as a JSON String message."""
        message = String()
        message.data = json.dumps(catalog, sort_keys=True, separators=(",", ":"))
        self._catalog_publisher.publish(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ModelCatalogNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.try_shutdown()
