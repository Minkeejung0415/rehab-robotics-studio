import { reconnectHardware } from '../../data/appDataSource';
import { useSystemStore } from '../../state/systemStore';
import type { EspHealthSnapshot } from '../../types/health';

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

export function HealthPanel() {
  const health = useSystemStore((state) => state.pairHealth);
  const openSim = useSystemStore((state) => state.openSimStatus);
  const addLog = useSystemStore((state) => state.addLog);
  const recording = health?.master?.recording;
  const state = recording?.state ?? 'idle';

  // Show the reconnect button when:
  //  1. Recording is in error state, OR
  //  2. Master reports a non-connected state, OR
  //  3. Master stream appears stale (connected but frame age > STALE_STREAM_MS) —
  //     this catches the "connected + 0 Hz" zombie state after a 1000 Hz overload.
  const recoveryNeeded =
    state === 'error' ||
    health?.master?.connection_state !== 'connected' ||
    isStale(health?.master);

  const retry = () => {
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
          <span>OpenSim IK angles</span>
          <strong>Waiting (requires calibration)</strong>
          <span>Model</span>
          <strong>{display(openSim?.visualization?.model_path, 'Not loaded')}</strong>
          <span>3D visualizer</span>
          <strong>
            {openSim?.visualization?.available
              ? 'Available'
              : display(openSim?.visualization?.reason, 'Unavailable')}
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
        <button className="mini-btn" onClick={retry}>
          {isStale(health?.master) ? 'Stream stale — Reconnect ROS' : 'Reconnect ROS'}
        </button>
      )}
    </section>
  );
}
