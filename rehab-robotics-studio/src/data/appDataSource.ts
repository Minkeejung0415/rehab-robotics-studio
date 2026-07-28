import type { DataSource } from './DataSource';
import { mockDataSource } from './MockDataSource';
import { RosbridgeDataSource, type ImuControlParameter } from './RosbridgeDataSource';
import { useSystemStore } from '../state/systemStore';

const sourceMode = import.meta.env.VITE_DATA_SOURCE || 'rosbridge';
let active: DataSource = mockDataSource;
let requestedRate = 1000;
let running = false;

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
  (connected) => useSystemStore.getState().setRosConnected(connected),
  () => useSystemStore.getState().setEspStreamActive(true),
  (health) => useSystemStore.getState().setPairHealth(health),
  undefined,
  (status) => useSystemStore.getState().setOpenSimStatus(status),
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
