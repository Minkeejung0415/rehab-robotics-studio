import type {
  LiveKneeAngleSnapshot,
  OpenSimIkStatusSnapshot,
  OpenSimJointStateSnapshot,
  OpenSimStatusSnapshot,
  RosStamp,
} from '../types/health';

export const IK_ANGLE_STALE_MS = 2_000;
export const OPEN_SIM_KNEE_COORDINATE = 'knee_angle_r';

const INVALID_STAMP_REASON = 'JointState source stamp is invalid';
const OUT_OF_ORDER_REASON = 'JointState source stamp is out of order';
const WAITING_REASON = 'Waiting for calibrated IK';
const STALE_REASON = 'JointState stale - no fresh angle for 2.0 s';

export interface FormattedLiveKneeAngle {
  isLive: boolean;
  valueText: string;
  statusText: string | null;
}

/** One fail-closed display contract for every product-angle surface. */
export function formatLiveKneeAngle(
  valueDeg: number | null | undefined,
): FormattedLiveKneeAngle {
  if (typeof valueDeg === 'number' && Number.isFinite(valueDeg)) {
    return {
      isLive: true,
      valueText: `${valueDeg.toFixed(1)} deg`,
      statusText: null,
    };
  }
  return {
    isLive: false,
    valueText: '—',
    statusText: WAITING_REASON,
  };
}

/**
 * Keep a chart trace only while both its current official value and every
 * buffered point are finite. A closed gate therefore clears immediately.
 */
export function selectLiveKneeAngleSeries(
  valueDeg: number | null | undefined,
  series: number[],
): number[] {
  return (
    typeof valueDeg === 'number'
    && Number.isFinite(valueDeg)
    && series.every(Number.isFinite)
  )
    ? series
    : [];
}

export interface LiveKneeAngleInput {
  openSimStatus: OpenSimStatusSnapshot | null | undefined;
  ikStatus: OpenSimIkStatusSnapshot | null | undefined;
  jointState: OpenSimJointStateSnapshot | null | undefined;
  nowMs: number;
  lastAcceptedStamp?: RosStamp | null;
}

export interface LiveKneeAngleTrackerOptions {
  nowMs?: () => number;
  schedule?: (callback: () => void, delayMs: number) => unknown;
  cancel?: (handle: unknown) => void;
  onTransition?: (snapshot: LiveKneeAngleSnapshot) => void;
}

function unavailable(
  state: 'waiting' | 'invalid' | 'stale',
  reason: string,
): LiveKneeAngleSnapshot {
  return { state, valueDeg: null, reason };
}

function normalizedIdentifier(value: unknown): string {
  return typeof value === 'string' ? value.trim() : '';
}

/**
 * Convert a backend reason code into bounded display text without leaking raw
 * objects, JSON, stack traces, or JavaScript sentinel strings.
 */
export function normalizeLiveKneeReason(value: unknown, fallback: string): string {
  if (typeof value !== 'string') return fallback;
  const trimmed = value.trim();
  if (
    trimmed === ''
    || trimmed === 'undefined'
    || trimmed === 'null'
    || trimmed === '[object Object]'
    || trimmed.startsWith('{')
    || trimmed.startsWith('[')
    || trimmed.includes('\n')
    || trimmed.includes('\r')
  ) {
    return fallback;
  }
  const normalized = trimmed.replace(/_+/g, ' ').replace(/\s+/g, ' ').slice(0, 160);
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

/** Validate each ROS stamp field independently; never combine them into JS nanoseconds. */
export function isValidRosStamp(stamp: RosStamp | null | undefined): stamp is RosStamp {
  return Boolean(
    stamp
    && Number.isSafeInteger(stamp.sec)
    && stamp.sec >= 0
    && Number.isSafeInteger(stamp.nanosec)
    && stamp.nanosec >= 0
    && stamp.nanosec < 1_000_000_000,
  );
}

/** Lexicographic ordering avoids overflowing Number's safe integer range. */
export function compareRosStamps(left: RosStamp, right: RosStamp): -1 | 0 | 1 {
  if (left.sec < right.sec) return -1;
  if (left.sec > right.sec) return 1;
  if (left.nanosec < right.nanosec) return -1;
  if (left.nanosec > right.nanosec) return 1;
  return 0;
}

export function liveKneeAngleTransitionSignature(
  snapshot: LiveKneeAngleSnapshot,
): string {
  return `${snapshot.state}\u0000${snapshot.reason}`;
}

function isStructurallyAcceptableJointState(
  jointState: OpenSimJointStateSnapshot,
): boolean {
  if (
    !isValidRosStamp(jointState.stamp)
    || jointState.names.length !== jointState.positions.length
    || !Number.isFinite(jointState.receivedAtMs)
    || jointState.receivedAtMs < 0
  ) {
    return false;
  }
  const kneeIndex = jointState.names.indexOf(OPEN_SIM_KNEE_COORDINATE);
  return kneeIndex >= 0 && Number.isFinite(jointState.positions[kneeIndex]);
}

/** Pure, fail-closed product-angle derivation. */
export function deriveLiveKneeAngle(input: LiveKneeAngleInput): LiveKneeAngleSnapshot {
  const calibration = input.openSimStatus?.calibration;
  if (calibration?.state !== 'CALIBRATED') {
    return unavailable('waiting', WAITING_REASON);
  }

  if (input.ikStatus?.solution_valid !== true) {
    return unavailable(
      'invalid',
      `IK invalid - ${normalizeLiveKneeReason(
        input.ikStatus?.reason,
        'No valid OpenSim IK solution',
      )}`,
    );
  }

  const activeCalibrationId = normalizedIdentifier(calibration.calibration_id);
  const ikCalibrationId = normalizedIdentifier(input.ikStatus.calibration_id);
  if (!activeCalibrationId || !ikCalibrationId) {
    return unavailable('invalid', 'IK calibration identity is missing');
  }
  if (activeCalibrationId !== ikCalibrationId) {
    return unavailable('invalid', 'IK calibration identity does not match');
  }

  const jointState = input.jointState;
  if (!jointState) {
    return unavailable('waiting', WAITING_REASON);
  }
  if (jointState.names.length !== jointState.positions.length) {
    return unavailable('invalid', 'JointState name and position arrays do not match');
  }
  if (!isValidRosStamp(jointState.stamp)) {
    return unavailable('invalid', INVALID_STAMP_REASON);
  }
  if (
    input.lastAcceptedStamp
    && isValidRosStamp(input.lastAcceptedStamp)
    && compareRosStamps(jointState.stamp, input.lastAcceptedStamp) < 0
  ) {
    return unavailable('invalid', OUT_OF_ORDER_REASON);
  }

  const kneeIndex = jointState.names.indexOf(OPEN_SIM_KNEE_COORDINATE);
  if (kneeIndex < 0) {
    return unavailable('invalid', `${OPEN_SIM_KNEE_COORDINATE} missing from JointState`);
  }
  const radians = jointState.positions[kneeIndex];
  if (!Number.isFinite(radians)) {
    return unavailable('invalid', `${OPEN_SIM_KNEE_COORDINATE} is not finite`);
  }

  if (
    !Number.isFinite(input.nowMs)
    || !Number.isFinite(jointState.receivedAtMs)
    || input.nowMs < 0
    || jointState.receivedAtMs < 0
    || input.nowMs < jointState.receivedAtMs
  ) {
    return unavailable('invalid', 'JointState receipt time is invalid');
  }
  if (input.nowMs - jointState.receivedAtMs > IK_ANGLE_STALE_MS) {
    return unavailable('stale', STALE_REASON);
  }

  return {
    state: 'live',
    // OpenSim's knee coordinate is zero at the calibrated straight reference
    // pose.  The user-facing clinical knee angle is supplementary: a straight
    // leg reads 180°, and flexion reduces the displayed angle.
    valueDeg: 180 - (radians * 180 / Math.PI),
    reason: '',
    sourceStamp: { ...jointState.stamp },
    receivedAtMs: jointState.receivedAtMs,
  };
}

/**
 * Stateful seam for transport/store wiring. It owns accepted stamp ordering,
 * cache clearing, stale scheduling, and transition-only notifications.
 */
export class LiveKneeAngleTracker {
  private readonly nowMs: () => number;
  private readonly schedule: (callback: () => void, delayMs: number) => unknown;
  private readonly cancel: (handle: unknown) => void;
  private readonly onTransition?: (snapshot: LiveKneeAngleSnapshot) => void;

  private openSimStatus: OpenSimStatusSnapshot | null = null;
  private ikStatus: OpenSimIkStatusSnapshot | null = null;
  private jointState: OpenSimJointStateSnapshot | null = null;
  private lastAcceptedStamp: RosStamp | null = null;
  private timer: unknown = null;
  private lastSignature: string | null = null;
  private current: LiveKneeAngleSnapshot = unavailable('waiting', WAITING_REASON);

  constructor(options: LiveKneeAngleTrackerOptions = {}) {
    this.nowMs = options.nowMs ?? (() => performance.now());
    this.schedule = options.schedule
      ?? ((callback, delayMs) => setTimeout(callback, delayMs));
    this.cancel = options.cancel ?? ((handle) => clearTimeout(handle as number));
    this.onTransition = options.onTransition;
    this.recompute();
  }

  setOpenSimStatus(status: OpenSimStatusSnapshot | null): LiveKneeAngleSnapshot {
    this.openSimStatus = status;
    if (status?.calibration?.state !== 'CALIBRATED') {
      this.jointState = null;
      this.lastAcceptedStamp = null;
    }
    return this.recompute();
  }

  setIkStatus(status: OpenSimIkStatusSnapshot | null): LiveKneeAngleSnapshot {
    this.ikStatus = status;
    return this.recompute();
  }

  setJointState(jointState: OpenSimJointStateSnapshot | null): LiveKneeAngleSnapshot {
    this.jointState = jointState;
    if (
      jointState
      && isStructurallyAcceptableJointState(jointState)
      && (
        !this.lastAcceptedStamp
        || compareRosStamps(jointState.stamp, this.lastAcceptedStamp) >= 0
      )
    ) {
      this.lastAcceptedStamp = { ...jointState.stamp };
    }
    return this.recompute();
  }

  evaluate(): LiveKneeAngleSnapshot {
    return this.recompute();
  }

  getSnapshot(): LiveKneeAngleSnapshot {
    return this.current;
  }

  dispose(): void {
    this.cancelTimer();
  }

  private cancelTimer(): void {
    if (this.timer !== null) {
      this.cancel(this.timer);
      this.timer = null;
    }
  }

  private recompute(): LiveKneeAngleSnapshot {
    this.cancelTimer();
    this.current = deriveLiveKneeAngle({
      openSimStatus: this.openSimStatus,
      ikStatus: this.ikStatus,
      jointState: this.jointState,
      nowMs: this.nowMs(),
      lastAcceptedStamp: this.lastAcceptedStamp,
    });

    const signature = liveKneeAngleTransitionSignature(this.current);
    if (signature !== this.lastSignature) {
      this.lastSignature = signature;
      this.onTransition?.(this.current);
    }

    if (this.current.state === 'live') {
      const ageMs = this.nowMs() - this.current.receivedAtMs;
      const delayMs = Math.max(1, IK_ANGLE_STALE_MS - ageMs + 1);
      this.timer = this.schedule(() => {
        this.timer = null;
        this.recompute();
      }, delayMs);
    }
    return this.current;
  }
}
