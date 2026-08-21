"""Offline deterministic tests for model_catalog_node.py.

Proves:
- MODEL-01: SHA-256 identity hash contract.
- MODEL-02: Frame enumeration from mock OpenSim model.
- MODEL-03: Fail-closed on missing/bad path or unavailable opensim bindings.

No live ROS, no real OpenSim, no hardware.
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


# ---------------------------------------------------------------------------
# ROS / dependency stubs — must be installed before importing the module.
# ---------------------------------------------------------------------------

def _install_ros_stubs() -> None:
    """Inject lightweight stubs for rclpy and message packages."""
    _backend_root = str(Path(__file__).parents[1])
    if _backend_root not in sys.path:
        sys.path.insert(0, _backend_root)

    # rclpy core
    rclpy = types.ModuleType("rclpy")
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.qos = types.ModuleType("rclpy.qos")
    rclpy.node.Node = type("Node", (), {})
    rclpy.qos.DurabilityPolicy = type("DurabilityPolicy", (), {"TRANSIENT_LOCAL": "transient_local"})
    rclpy.qos.ReliabilityPolicy = type("ReliabilityPolicy", (), {"RELIABLE": "reliable"})
    rclpy.qos.QoSProfile = type("QoSProfile", (), {"__init__": lambda self, **kwargs: self.__dict__.update(kwargs)})
    rclpy.ok = lambda: True
    rclpy.init = lambda *a, **k: None
    rclpy.spin = lambda *a, **k: None
    rclpy.try_shutdown = lambda *a, **k: None
    sys.modules.setdefault("rclpy", rclpy)
    sys.modules.setdefault("rclpy.node", rclpy.node)
    sys.modules.setdefault("rclpy.qos", rclpy.qos)

    # rcl_interfaces
    rcl_iface = types.ModuleType("rcl_interfaces")
    rcl_iface.msg = types.ModuleType("rcl_interfaces.msg")
    rcl_iface.msg.SetParametersResult = type("SetParametersResult", (), {})
    sys.modules.setdefault("rcl_interfaces", rcl_iface)
    sys.modules.setdefault("rcl_interfaces.msg", rcl_iface.msg)

    # sensor_msgs
    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs.msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs.msg.Imu = type("Imu", (), {})
    sys.modules.setdefault("sensor_msgs", sensor_msgs)
    sys.modules.setdefault("sensor_msgs.msg", sensor_msgs.msg)

    # std_msgs
    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = types.ModuleType("std_msgs.msg")
    for name in ("Float32MultiArray", "Header", "String"):
        setattr(
            std_msgs.msg,
            name,
            type(name, (), {"__init__": lambda self, **kw: None}),
        )
    sys.modules.setdefault("std_msgs", std_msgs)
    sys.modules.setdefault("std_msgs.msg", std_msgs.msg)

    # rehab_robotics_interfaces (srv stubs for transitive imports)
    rri = types.ModuleType("rehab_robotics_interfaces")
    rri.srv = types.ModuleType("rehab_robotics_interfaces.srv")
    rri.msg = types.ModuleType("rehab_robotics_interfaces.msg")
    for srv_name in (
        "SetAssignment",
        "ApplyMapping",
        "GetMappingState",
        "ResetMapping",
    ):
        setattr(rri.srv, srv_name, type(srv_name, (), {}))
    sys.modules.setdefault("rehab_robotics_interfaces", rri)
    sys.modules.setdefault("rehab_robotics_interfaces.srv", rri.srv)
    sys.modules.setdefault("rehab_robotics_interfaces.msg", rri.msg)


_install_ros_stubs()


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_catalog_module():
    """Import model_catalog_node without live ROS/OpenSim."""
    backend_root = Path(__file__).parents[1]
    node_path = backend_root / "rehab_robotics_bridge" / "model_catalog_node.py"
    spec = importlib.util.spec_from_file_location(
        "rehab_robotics_bridge.model_catalog_node", node_path
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


catalog_mod = _load_catalog_module()


# ---------------------------------------------------------------------------
# Shared test doubles
# ---------------------------------------------------------------------------

class _Parameter:
    def __init__(self, value):
        self.value = value


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class _Logger:
    def info(self, *a, **kw):
        pass

    def warning(self, *a, **kw):
        pass

    def error(self, *a, **kw):
        pass


class _StubNode:
    """Minimal ROS 2 Node test double."""

    parameter_overrides: dict = {}

    def __init__(self, name="test_node"):
        self.node_name = name
        self.parameters: dict = {}
        self.publishers = []
        self.timers = []
        self.subscriptions = []
        self._logger = _Logger()

    def declare_parameter(self, name, default):
        value = self.parameter_overrides.get(name, default)
        self.parameters[name] = value
        return _Parameter(value)

    def get_parameter(self, name):
        return _Parameter(self.parameters.get(name, ""))

    def create_publisher(self, msg_type, topic, depth):
        pub = _Publisher()
        pub.topic = topic
        self.publishers.append(pub)
        return pub

    def create_timer(self, period, callback):
        timer = types.SimpleNamespace(period=period, callback=callback)
        self.timers.append(timer)
        return timer

    def create_subscription(self, msg_type, topic, callback, qos):
        sub = types.SimpleNamespace(topic=topic, callback=callback)
        self.subscriptions.append(sub)
        return sub

    def get_logger(self):
        return self._logger


# ---------------------------------------------------------------------------
# Helper: build a minimal mock opensim module
# ---------------------------------------------------------------------------

def _make_mock_opensim(body_names: list[str], offset_frames: list[dict] | None = None):
    """Return a mock opensim module with a Model class driven by ``body_names``.

    Args:
        body_names: Names of bodies exposed by the mock model's getBodySet().
        offset_frames: Optional list of dicts with keys ``name`` and ``parent``
            for PhysicalOffsetFrame components returned by getComponentsList().
    """
    if offset_frames is None:
        offset_frames = []

    class _Body:
        def __init__(self, name: str):
            self._name = name

        def getName(self) -> str:
            return self._name

    class _BodySet:
        def __init__(self, bodies):
            self._bodies = bodies

        def getSize(self) -> int:
            return len(self._bodies)

        def get(self, i: int):
            return self._bodies[i]

    class _OffsetFrame:
        def __init__(self, name: str, parent_name: str):
            self._name = name
            self._parent_name = parent_name
            # Mark concrete class so the production code recognises it.
            self._class_name = "PhysicalOffsetFrame"

        def getConcreteClassName(self) -> str:
            return self._class_name

        def getName(self) -> str:
            return self._name

        def getParentFrame(self):
            return types.SimpleNamespace(getName=lambda: self._parent_name)

    bodies = [_Body(n) for n in body_names]
    frames = [_OffsetFrame(f["name"], f["parent"]) for f in offset_frames]

    class _Model:
        def __init__(self, path: str):
            self._path = path

        def getBodySet(self):
            return _BodySet(bodies)

        def getComponentsList(self):
            # Return all bodies (non-PhysicalOffsetFrame) + offset frames;
            # the production code filters by getConcreteClassName.
            non_frame_bodies = [
                types.SimpleNamespace(
                    getConcreteClassName=lambda n=b._name: "Body",
                    getName=lambda n=b._name: n,
                )
                for b in bodies
            ]
            return non_frame_bodies + frames

    mock = types.SimpleNamespace(Model=_Model)
    return mock


# ===========================================================================
# Test suite 1: Pure-function tests (compute_model_hash, enumerate_compatible_frames)
# ===========================================================================

class ModelCatalogPureFunctionTest(unittest.TestCase):
    """Tests for compute_model_hash and enumerate_compatible_frames."""

    # ------------------------------------------------------------------
    # compute_model_hash
    # ------------------------------------------------------------------

    def test_compute_model_hash_correct(self):
        """SHA-256 of known bytes matches hashlib reference."""
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        with tempfile.NamedTemporaryFile(suffix=".osim", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        try:
            result = catalog_mod.compute_model_hash(tmp_path)
            self.assertEqual(result, expected)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_compute_model_hash_empty_file(self):
        """SHA-256 of an empty file equals sha256(b'').hexdigest()."""
        expected = hashlib.sha256(b"").hexdigest()
        with tempfile.NamedTemporaryFile(suffix=".osim", delete=False) as f:
            tmp_path = f.name
        try:
            result = catalog_mod.compute_model_hash(tmp_path)
            self.assertEqual(result, expected)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_compute_model_hash_missing_path_raises(self):
        """FileNotFoundError raised when path does not exist."""
        with self.assertRaises(FileNotFoundError):
            catalog_mod.compute_model_hash("/nonexistent/path/missing.osim")

    def test_hash_changes_on_file_change(self):
        """Different file contents produce different hash values."""
        content_a = b"content alpha"
        content_b = b"content beta"
        with tempfile.NamedTemporaryFile(suffix=".osim", delete=False) as fa:
            fa.write(content_a)
            path_a = fa.name
        with tempfile.NamedTemporaryFile(suffix=".osim", delete=False) as fb:
            fb.write(content_b)
            path_b = fb.name
        try:
            hash_a = catalog_mod.compute_model_hash(path_a)
            hash_b = catalog_mod.compute_model_hash(path_b)
            self.assertNotEqual(hash_a, hash_b)
        finally:
            Path(path_a).unlink(missing_ok=True)
            Path(path_b).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # enumerate_compatible_frames
    # ------------------------------------------------------------------

    def _make_tmp_osim(self) -> str:
        """Create a throwaway .osim file and return its path."""
        with tempfile.NamedTemporaryFile(suffix=".osim", delete=False) as f:
            f.write(b"<dummy/>")
            return f.name

    def test_enumerate_compatible_frames_excludes_ground(self):
        """Ground body is excluded; non-Ground bodies are included."""
        mock_opensim = _make_mock_opensim(["ground", "femur_r", "tibia_r"])
        tmp_path = self._make_tmp_osim()
        try:
            result = catalog_mod.enumerate_compatible_frames(tmp_path, mock_opensim)
            segments = [r["segment"] for r in result]
            self.assertNotIn("ground", segments)
            self.assertEqual(sorted(segments), ["femur_r", "tibia_r"])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_enumerate_compatible_frames_empty_model(self):
        """Model with only a Ground body returns an empty list."""
        mock_opensim = _make_mock_opensim(["ground"])
        tmp_path = self._make_tmp_osim()
        try:
            result = catalog_mod.enumerate_compatible_frames(tmp_path, mock_opensim)
            self.assertEqual(result, [])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_enumerate_compatible_frames_no_bodies_at_all(self):
        """Model with no bodies at all returns an empty list."""
        mock_opensim = _make_mock_opensim([])
        tmp_path = self._make_tmp_osim()
        try:
            result = catalog_mod.enumerate_compatible_frames(tmp_path, mock_opensim)
            self.assertEqual(result, [])
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_enumerate_compatible_frames_read_only(self):
        """enumerate_compatible_frames never calls setUseVisualizer or initSystem."""
        called_methods: list[str] = []

        # Override _Model to record setter calls.
        base_opensim = _make_mock_opensim(["femur_r"])
        original_model_cls = base_opensim.Model

        class _InstrumentedModel(original_model_cls):
            def setUseVisualizer(self, *a, **kw):
                called_methods.append("setUseVisualizer")

            def initSystem(self, *a, **kw):
                called_methods.append("initSystem")

        base_opensim.Model = _InstrumentedModel
        tmp_path = self._make_tmp_osim()
        try:
            catalog_mod.enumerate_compatible_frames(tmp_path, base_opensim)
            self.assertNotIn("setUseVisualizer", called_methods)
            self.assertNotIn("initSystem", called_methods)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_enumerate_compatible_frames_result_is_sorted(self):
        """Results are sorted by (segment, frame) for deterministic output."""
        mock_opensim = _make_mock_opensim(["tibia_r", "femur_r", "pelvis"])
        tmp_path = self._make_tmp_osim()
        try:
            result = catalog_mod.enumerate_compatible_frames(tmp_path, mock_opensim)
            segments = [r["segment"] for r in result]
            self.assertEqual(segments, sorted(segments))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_enumerate_compatible_frames_missing_file_raises(self):
        """FileNotFoundError raised when model_path does not exist."""
        mock_opensim = _make_mock_opensim(["femur_r"])
        with self.assertRaises(FileNotFoundError):
            catalog_mod.enumerate_compatible_frames(
                "/nonexistent/path/missing.osim", mock_opensim
            )


# ===========================================================================
# Test suite 2: ModelCatalogNode publish behavior
# ===========================================================================

def _make_catalog_node(parameter_overrides: dict | None = None):
    """Instantiate ModelCatalogNode backed by _StubNode.

    The production class inherits from rclpy.node.Node, which is already
    stubbed.  We patch the stub's base at module-scope so that
    ModelCatalogNode.__init__ calls go to _StubNode methods.
    """
    # Patch the rclpy.node.Node stub to be _StubNode.
    sys.modules["rclpy"].node.Node = _StubNode
    catalog_mod_reloaded = _load_catalog_module()

    # Apply parameter overrides via class attribute (mirroring test_opensim_node.py).
    class _OverrideStubNode(_StubNode):
        pass

    if parameter_overrides:
        _OverrideStubNode.parameter_overrides = parameter_overrides
    else:
        _OverrideStubNode.parameter_overrides = {}

    sys.modules["rclpy"].node.Node = _OverrideStubNode
    mod = _load_catalog_module()
    node = mod.ModelCatalogNode()
    return node, mod


class ModelCatalogNodePublishTest(unittest.TestCase):
    """Tests for ModelCatalogNode._build_and_publish_catalog and _on_catalog_timer."""

    def setUp(self):
        """Restore rclpy.node.Node stub after each test."""
        self._original_node_cls = sys.modules["rclpy"].node.Node

    def tearDown(self):
        sys.modules["rclpy"].node.Node = self._original_node_cls

    def _get_published_json(self, node) -> dict:
        """Return the last published JSON dict from the catalog publisher."""
        pub = node._catalog_publisher
        self.assertGreater(
            len(pub.messages), 0, "No messages were published."
        )
        return json.loads(pub.messages[-1].data)

    def _count_publishes(self, node) -> int:
        return len(node._catalog_publisher.messages)

    # ------------------------------------------------------------------

    def test_empty_model_path_publishes_no_model_path_error(self):
        """Empty opensim_model_path yields error_reason=no_model_path.

        The node does not publish on startup when the default path is empty
        (both _last_model_path and new_path start as "").  We invoke
        _build_and_publish_catalog directly to test the branch logic.
        """
        node, _ = _make_catalog_node({"opensim_model_path": ""})
        node._build_and_publish_catalog("")
        data = self._get_published_json(node)
        self.assertEqual(data["error_reason"], "no_model_path")
        self.assertEqual(data["frame_list"], [])
        self.assertEqual(data["model_hash"], "")

    def test_missing_file_publishes_not_found_error(self):
        """Non-existent model path yields error_reason=model_path_not_found."""
        node, _ = _make_catalog_node(
            {"opensim_model_path": "/nonexistent/missing.osim"}
        )
        data = self._get_published_json(node)
        self.assertEqual(data["error_reason"], "model_path_not_found")

    def test_opensim_unavailable_publishes_bindings_error(self):
        """ImportError on opensim yields error_reason=opensim_bindings_unavailable."""
        with tempfile.NamedTemporaryFile(suffix=".osim", delete=False) as f:
            f.write(b"<dummy/>")
            tmp_path = f.name
        try:
            node, mod = _make_catalog_node({"opensim_model_path": tmp_path})
            # Force opensim to be unavailable.
            opensim_backup = sys.modules.pop("opensim", None)
            original_import = importlib.import_module

            def _raise_import(name, *a, **kw):
                if name == "opensim":
                    raise ImportError("opensim not installed")
                return original_import(name, *a, **kw)

            importlib.import_module = _raise_import
            try:
                # Reset tracked path so a fresh publish is triggered.
                node._last_model_path = ""
                node._build_and_publish_catalog(tmp_path)
                data = self._get_published_json(node)
                self.assertEqual(
                    data["error_reason"], "opensim_bindings_unavailable"
                )
                # Hash must be present (computed before import attempt).
                expected_hash = hashlib.sha256(b"<dummy/>").hexdigest()
                self.assertEqual(data["model_hash"], expected_hash)
                self.assertEqual(data["frame_list"], [])
            finally:
                importlib.import_module = original_import
                if opensim_backup is not None:
                    sys.modules["opensim"] = opensim_backup
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_schema_version_in_all_error_outputs(self):
        """schema_version == 'rehab.model_catalog.1' in every error output."""
        expected_schema = "rehab.model_catalog.1"

        # Case 1: empty path — call _build_and_publish_catalog directly because
        # the node skips the initial timer call when path is already "".
        node1, _ = _make_catalog_node({"opensim_model_path": ""})
        node1._build_and_publish_catalog("")
        data1 = self._get_published_json(node1)
        self.assertEqual(data1["schema_version"], expected_schema)

        # Case 2: missing file — __init__ timer fires and publishes.
        node2, _ = _make_catalog_node(
            {"opensim_model_path": "/nonexistent/missing.osim"}
        )
        data2 = self._get_published_json(node2)
        self.assertEqual(data2["schema_version"], expected_schema)

    def test_no_republish_on_same_path(self):
        """Calling _on_catalog_timer twice with the same path only publishes once."""
        node, _ = _make_catalog_node({"opensim_model_path": ""})
        count_after_init = self._count_publishes(node)
        # Call timer again — path hasn't changed.
        node._on_catalog_timer()
        count_after_second = self._count_publishes(node)
        self.assertEqual(count_after_init, count_after_second)

    def test_on_catalog_timer_publishes_on_path_change(self):
        """_on_catalog_timer publishes when path changes between calls."""
        node, _ = _make_catalog_node({"opensim_model_path": ""})
        count_before = self._count_publishes(node)

        # Simulate operator changing the parameter to a new (still missing) path.
        node.parameters["opensim_model_path"] = "/nonexistent/new.osim"
        node._on_catalog_timer()
        count_after = self._count_publishes(node)
        self.assertGreater(count_after, count_before)

    def test_catalog_published_on_load(self):
        """ModelCatalogNode publishes a catalog immediately on __init__ when path is non-empty.

        When opensim_model_path is a non-empty path, the startup _on_catalog_timer
        call transitions from "" to that path and triggers a publish.  Here we use
        a path to a missing file so the call short-circuits without needing OpenSim.
        """
        node, _ = _make_catalog_node(
            {"opensim_model_path": "/nonexistent/startup.osim"}
        )
        count = self._count_publishes(node)
        self.assertGreaterEqual(count, 1)
        data = self._get_published_json(node)
        for required_key in ("schema_version", "model_hash", "frame_list"):
            self.assertIn(required_key, data)


if __name__ == "__main__":
    unittest.main()
