import type { DataSource } from './DataSource';
import { mockDataSource } from './MockDataSource';
import { RosbridgeDataSource, type ImuControlParameter } from './RosbridgeDataSource';
import { LiveKneeAngleTracker, normalizeLiveKneeReason } from './liveKneeAngle';
import { useSystemStore } from '../state/systemStore';
import { useMappingStore } from '../state/mappingStore';

const sourceMode = import.meta.env.VITE_DATA_SOURCE || 'rosbridge';
let active: DataSource = mockDataSource;
let requestedRate = 1000;
let running = false;
let visualizerRequest: Promise<{ success: boolean; message: string }> | null = null;

const liveKneeAngleTracker = new LiveKneeAngleTracker({
  onTransition: (snapshot) => useSystemStore.getState().setLiveKneeAngle(snapshot),
});

const rosbridgeDataSource = new RosbridgeDataSource(
  undefined,
  undefined,
  undefined,
  () => {
    if (active !== rosbridgeDataSource || !running) return;
    useSystemStore.getState().setRosConnected(false);
    useSystemStore.getState().setEspStreamActive(false);
    active = mockDataSource;
    active.start(requestedRate);
  },
  (connected) => {
    const store = useSystemStore.getState();
    store.setRosConnected(connected);
    if (!connected) {
      store.setOpenSimJointState(null);
      store.setLiveKneeAngle(liveKneeAngleTracker.setJointState(null));
    }
  },
  () => useSystemStore.getState().setEspStreamActive(true),
  (health) => useSystemStore.getState().setPairHealth(health),
  undefined,
  (status) => {
    const store = useSystemStore.getState();
    store.setOpenSimStatus(status);
    store.setLiveKneeAngle(liveKneeAngleTracker.setOpenSimStatus(status));
  },
  (status) => {
    const store = useSystemStore.getState();
    store.setOpenSimIkStatus(status);
    store.setLiveKneeAngle(liveKneeAngleTracker.setIkStatus(status));
  },
  (jointState) => {
    const store = useSystemStore.getState();
    store.setOpenSimJointState(jointState);
    store.setLiveKneeAngle(liveKneeAngleTracker.setJointState(jointState));
  },
  // Phase 24: Mapping workspace callbacks (positions 12-16, per D-25)
  (catalog) => useMappingStore.getState().updateFromCatalog(catalog),
  (state) => useMappingStore.getState().updateFromMappingCurrent(state),
  (registry) => useMappingStore.getState().updateFromFleetRegistry(registry.devices ?? []),
  (status) => useMappingStore.getState().updateFromCalibrationStatus(status),
  (validity) => useMappingStore.getState().updateInputValidity(validity),
);

if (sourceMode !== 'mock') active = rosbridgeDataSource;

/**
 * Application-level source selection. Real ROS data is the default; mock data
 * keeps the editor usable when rosbridge is intentionally not running.
 */
export const appDataSource: DataSource = {
  start(rateHz) {
    requestedRate = rateHz;
    running = true;
    active.start(rateHz);
  },
  stop() {
    running = false;
    active.stop();
  },
  pause() { active.pause(); },
  resume() { active.resume(); },
  setSampleRate(rateHz) {
    requestedRate = rateHz;
    active.setSampleRate(rateHz);
  },
  subscribe(callback) {
    const unsubscribers = [mockDataSource.subscribe(callback), rosbridgeDataSource.subscribe(callback)];
    return () => unsubscribers.forEach((unsubscribe) => unsubscribe());
  },
};

/** Request SD recording through the master ESP32's plugin-compatible rec-v1 path. */
export async function setHardwareRecording(on: boolean): Promise<{ success: boolean; message: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active' };
  }
  return rosbridgeDataSource.setRecording(on);
}

/** Begin OpenSim reference-pose calibration capture via rosbridge Trigger. */
export async function captureOpenSimCalibration(): Promise<{ success: boolean; message: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active' };
  }
  return rosbridgeDataSource.captureCalibration();
}

/** Clear OpenSim calibration offsets via rosbridge Trigger. */
export async function clearOpenSimCalibration(): Promise<{ success: boolean; message: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active' };
  }
  return rosbridgeDataSource.clearCalibration();
}

/**
 * Request the fixed backend-owned native OpenSim visualizer action.
 * Concurrent activations share one bounded request; failures remain in the
 * store until a retry or backend Opening/Open transition replaces them.
 */
export function openOpenSimVisualizer(): Promise<{ success: boolean; message: string }> {
  if (visualizerRequest) return visualizerRequest;

  const store = useSystemStore.getState();
  store.setOpenSimVisualizerRequest({ state: 'opening', reason: '' });
  if (active !== rosbridgeDataSource) {
    const reason = 'Live ROS ESP32 stream is not active';
    store.setOpenSimVisualizerRequest({ state: 'failed', reason });
    return Promise.resolve({ success: false, message: reason });
  }

  visualizerRequest = rosbridgeDataSource.openVisualizer()
    .then((result) => {
      if (!result.success) {
        const reason = normalizeLiveKneeReason(
          result.message,
          'OpenSim visualizer could not open',
        );
        useSystemStore.getState().setOpenSimVisualizerRequest({
          state: 'failed',
          reason,
        });
        return { success: false, message: reason };
      }
      return result;
    })
    .finally(() => {
      visualizerRequest = null;
    });
  return visualizerRequest;
}

/** Apply the ESP32 pair sample rate selected by the acquisition block. */
export async function setHardwareSampleRate(rateHz: number): Promise<{ success: boolean; message: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active' };
  }
  return rosbridgeDataSource.requestSampleRate(rateHz);
}

/** Apply one live IMU setting and leave the graph unchanged until it is confirmed. */
export async function setHardwareImuControl(
  name: ImuControlParameter,
  value: number | boolean,
): Promise<{ success: boolean; message: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active' };
  }
  return rosbridgeDataSource.requestImuControl(name, value);
}

/** Reopen rosbridge after a transport error without changing acquisition settings. */
export function reconnectHardware(): { success: boolean; message: string } {
  if (active !== rosbridgeDataSource || !running) {
    return { success: false, message: 'Start acquisition before reconnecting the ROS bridge' };
  }
  rosbridgeDataSource.stop();
  rosbridgeDataSource.start(requestedRate);
  return { success: true, message: 'Reconnecting to the ROS bridge' };
}

/** Submit a per-device segment assignment to the backend via SetAssignment service. */
export async function callMappingSetAssignment(
  deviceId: string,
  segment: string,
  frame: string,
  state: string,
): Promise<{ success: boolean; message: string; outcome: string; detail: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active', outcome: '', detail: '' };
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return rosbridgeDataSource.callSetAssignment(deviceId, segment, frame, state) as any;
}

/** Atomically apply all current assignments via ApplyMapping service. */
export async function callMappingApply(
  expectedRevision: number,
): Promise<{ success: boolean; message: string; outcome: string; appliedRevision: number; detail: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active', outcome: '', appliedRevision: 0, detail: '' };
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return rosbridgeDataSource.callApplyMapping(expectedRevision) as any;
}

/** Reset all assignments for the given model hash via ResetMapping service. */
export async function callMappingReset(
  modelHash: string | null,
): Promise<{ success: boolean; message: string; outcome: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active', outcome: '' };
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return rosbridgeDataSource.callResetMapping(modelHash ?? '') as any;
}

/** Trigger LED flash on a device for physical identification via IdentifyDevice service. */
export async function callMappingIdentifyDevice(
  deviceId: string,
  timeoutMs = 5000,
): Promise<{ success: boolean; message: string; outcome: string }> {
  if (active !== rosbridgeDataSource) {
    return { success: false, message: 'Live ROS ESP32 stream is not active', outcome: '' };
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return rosbridgeDataSource.callIdentifyDevice(deviceId, timeoutMs) as any;
}
