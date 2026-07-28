import type { OpenSimStatusSnapshot } from '../../types/health';

function display(value: string | number | null | undefined, fallback = 'Unknown'): string {
  return value === null || value === undefined || value === '' ? fallback : String(value);
}

/** Pure helper for OpenSim calibration status rows (unit-tested without React render). */
export function formatCalibrationStatus(snapshot: OpenSimStatusSnapshot | null | undefined): {
  state: string;
  reason: string;
} {
  const state = display(snapshot?.calibration?.state, 'UNCALIBRATED');
  const reason = String(snapshot?.calibration?.reason ?? '');
  return { state, reason };
}
