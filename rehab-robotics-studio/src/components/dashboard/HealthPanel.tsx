import { normalizeLiveKneeReason } from '../../data/liveKneeAngle';
import { useSystemStore } from '../../state/systemStore';
import type {
  EspHealthSnapshot,
  LiveKneeAngleSnapshot,
  OpenSimIkStatusSnapshot,
  OpenSimStatusSnapshot,
  OpenSimVisualizerRequestSnapshot,
} from '../../types/health';
import { formatCalibrationStatus } from './calibrationStatus';

/**
 * Frame age above this threshold (ms) is treated as a stale / zombie stream.
 * At 100 Hz a frame arrives every 10 ms; 5 000 ms = 500× the expected interval.
 * At the minimum supported rate (1 Hz) a frame arrives every 1 000 ms, so this
 * threshold is still conservative enough to avoid false positives.
 */
const STALE_STREAM_MS = 5_000;

function display(value: string | number | null | undefined, fallback: string | number = 'Unknown') {
  return value === null || value === undefined || value === '' ? fallback : String(value);
}

function nodeState(node: EspHealthSnapshot | null | undefined) {
  return node?.connection_state === 'connected' ? 'ok' : 'warn';
}

function isStale(node: EspHealthSnapshot | null | undefined): boolean {
  if (!node) return false;
  const age = node.last_frame_age_ms;
  if (age === null || age === undefined) return false;
  return age > STALE_STREAM_MS;
}

function NodeHealth({ label, node }: { label: string; node: EspHealthSnapshot | null | undefined }) {
  const stale = isStale(node);
  return (
    <div className="health-node">
      <strong>{label}</strong>
      <span className={`health-state ${nodeState(node)}`}>{display(node?.connection_state)}</span>
      <span className={stale ? 'health-stale' : ''}>
        {display(node?.observed_stream_rate_hz, '0')} Hz live
      </span>
      <span className={stale ? 'health-stale' : ''}>
        {display(node?.last_frame_age_ms, 'No')} ms frame age{stale ? ' ⚠' : ''}
      </span>
      <span>{display(node?.reconnect_count, 0)} reconnects</span>
    </div>
  );
}

export type OpenSimHealthTone = 'waiting' | 'attention' | 'ok' | 'fault';

export interface OpenSimHealthView {
  calibrationState: string;
  calibrationReason: string;
  ikSolution: string;
  ikInputAge: string;
  calibrationId: string;
  kneeAngle: string;
  model: string;
  visualizer: string;
  visualizerTone: OpenSimHealthTone;
}

function normalizedReason(value: unknown, fallback = 'Unknown reason'): string {
  return normalizeLiveKneeReason(value, fallback);
}

export function formatOpenSimHealth(
  openSim: OpenSimStatusSnapshot | null | undefined,
  ikStatus: OpenSimIkStatusSnapshot | null | undefined,
  liveKneeAngle: LiveKneeAngleSnapshot,
  visualizerRequest: OpenSimVisualizerRequestSnapshot,
): OpenSimHealthView {
  const calibration = formatCalibrationStatus(openSim);
  const backendVisualizerState = openSim?.visualization?.state?.toLowerCase();
  const backendVisualizerReason = openSim?.visualization?.reason;

  let visualizer = 'Waiting';
  let visualizerTone: OpenSimHealthTone = 'waiting';
  if (backendVisualizerState === 'opening') {
    visualizer = 'Opening…';
    visualizerTone = 'attention';
  } else if (backendVisualizerState === 'open') {
    visualizer = 'Open';
    visualizerTone = 'ok';
  } else if (visualizerRequest.state === 'opening') {
    visualizer = 'Opening…';
    visualizerTone = 'attention';
  } else if (visualizerRequest.state === 'failed') {
    visualizer = `Failed — ${normalizedReason(visualizerRequest.reason)}`;
    visualizerTone = 'fault';
  } else if (
    backendVisualizerState === 'failed'
    || backendVisualizerState === 'unavailable'
    || openSim?.visualization?.available === false
  ) {
    const label = backendVisualizerState === 'failed' ? 'Failed' : 'Unavailable';
    visualizer = `${label} — ${normalizedReason(
      backendVisualizerReason,
      'OpenSim visualizer is unavailable',
    )}`;
    visualizerTone = 'fault';
  }

  let ikSolution = 'Waiting';
  if (ikStatus?.solution_valid === true) {
    ikSolution = 'Valid';
  } else if (ikStatus?.solution_valid === false) {
    ikSolution = `Invalid — ${normalizedReason(
      ikStatus.reason,
      'No valid OpenSim IK solution',
    )}`;
  }

  const inputAge = ikStatus?.input_age_s;
  const kneeAngle = liveKneeAngle.state === 'live'
    ? `${liveKneeAngle.valueDeg.toFixed(1)} deg`
    : liveKneeAngle.state === 'stale'
      ? 'Stale'
      : 'Waiting for calibrated IK';

  return {
    calibrationState: calibration.state,
    calibrationReason: calibration.reason
      ? normalizedReason(calibration.reason)
      : '—',
    ikSolution,
    ikInputAge: Number.isFinite(inputAge) && Number(inputAge) >= 0
      ? `${Number(inputAge).toFixed(2)} s`
      : '—',
    calibrationId: display(openSim?.calibration?.calibration_id, '—'),
    kneeAngle,
    model: display(openSim?.visualization?.model_path, 'Not loaded'),
    visualizer,
    visualizerTone,
  };
}

function visualizerClass(tone: OpenSimHealthTone): string {
  if (tone === 'fault') return 'health-error';
  if (tone === 'ok') return 'recording-finalized';
  if (tone === 'attention') return 'recording-finalizing';
  return '';
}

export function HealthPanel() {
  const health = useSystemStore((state) => state.pairHealth);
  const openSim = useSystemStore((state) => state.openSimStatus);
  const ikStatus = useSystemStore((state) => state.openSimIkStatus);
  const liveKneeAngle = useSystemStore((state) => state.liveKneeAngle);
  const visualizerRequest = useSystemStore((state) => state.openSimVisualizerRequest);
  const addLog = useSystemStore((state) => state.addLog);
  const recording = health?.master?.recording;
  const state = recording?.state ?? 'idle';
  const openSimHealth = formatOpenSimHealth(
    openSim,
    ikStatus,
    liveKneeAngle,
    visualizerRequest,
  );

  // Show the reconnect button when:
  //  1. Recording is in error state, OR
  //  2. Master reports a non-connected state, OR
  //  3. Master stream appears stale (connected but frame age > STALE_STREAM_MS) —
  //     this catches the "connected + 0 Hz" zombie state after a 1000 Hz overload.
  const recoveryNeeded =
    state === 'error' ||
    health?.master?.connection_state !== 'connected' ||
    isStale(health?.master);

  const retry = async () => {
    const { reconnectHardware } = await import('../../data/appDataSource');
    const result = reconnectHardware();
    addLog(result.success ? 'INFO' : 'ERROR', result.message);
  };

  return (
    <section className="dash-panel health-panel">
      <div className="dash-head">
        <h3>Acquisition Health</h3>
        <span className={`motor-pill ${health?.pair_available ? 'enabled' : 'fault'}`}>
          {health?.pair_available ? 'PAIR ONLINE' : 'PAIR WAITING'}
        </span>
      </div>
      <div className="health-grid">
        <NodeHealth label="MASTER" node={health?.master} />
        <NodeHealth label="SLAVE" node={health?.slave} />
      </div>
      <div className="recording-health">
        <div className="dash-head">
          <h3>OpenSim Live Link</h3>
          <span className={`status-badge ${openSim ? 'recording-recording' : 'recording-idle'}`}>
            {openSim ? 'CONNECTED' : 'WAITING'}
          </span>
        </div>
        <div className="kv-grid">
          <span>Master quaternion</span>
          <strong>{display(openSim?.sensors?.master?.state, 'Waiting')}</strong>
          <span>Slave quaternion</span>
          <strong>{display(openSim?.sensors?.slave?.state, 'Waiting')}</strong>
          <span>Calibration state</span>
          <strong>{openSimHealth.calibrationState}</strong>
          <span>Calibration reason</span>
          <strong>{openSimHealth.calibrationReason}</strong>
          <span>IK solution</span>
          <strong>{openSimHealth.ikSolution}</strong>
          <span>IK input age</span>
          <strong>{openSimHealth.ikInputAge}</strong>
          <span>Calibration ID</span>
          <strong>{openSimHealth.calibrationId}</strong>
          <span>OpenSim knee angle</span>
          <strong>{openSimHealth.kneeAngle}</strong>
          <span>Model</span>
          <strong>{openSimHealth.model}</strong>
          <span>3D visualizer</span>
          <strong
            className={visualizerClass(openSimHealth.visualizerTone)}
            role="status"
            aria-live="polite"
          >
            {openSimHealth.visualizer}
          </strong>
        </div>
      </div>
      <div className="recording-health">
        <div className="dash-head">
          <h3>SD Recording</h3>
          <span className={`status-badge recording-${state}`}>{state.toUpperCase()}</span>
        </div>
        <div className="kv-grid">
          <span>Session</span><strong>{display(recording?.session_id, 'No session')}</strong>
          <span>Samples</span><strong>{display(recording?.saved_samples)}</strong>
          <span>File</span><strong>{display(recording?.file_byte_size, 'Awaiting final metadata')}</strong>
          <span>Checksum</span><strong>{display(recording?.file_checksum, 'Awaiting final metadata')}</strong>
          {recording?.error && <><span>Error</span><strong className="health-error">{recording.error}</strong></>}
        </div>
        {state === 'finalized' && (
          <p className="health-note">SD file finalized. Use the recorded session ID when exporting the master SD card.</p>
        )}
        {state === 'finalizing' && (
          <p className="health-note">Finalization is in progress. Keep the master powered until the session is finalized.</p>
        )}
      </div>
      {recoveryNeeded && (
        <button className="mini-btn" onClick={() => void retry()}>
          {isStale(health?.master) ? 'Stream stale — Reconnect ROS' : 'Reconnect ROS'}
        </button>
      )}
    </section>
  );
}
