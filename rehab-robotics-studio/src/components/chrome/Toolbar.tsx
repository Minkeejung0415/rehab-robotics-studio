import { useRef, useState } from 'react';
import { useRuntimeStore } from '../../state/runtimeStore';
import { useSystemStore } from '../../state/systemStore';
import { actions } from '../../state/actions';
import { Toast } from '../common/Toast';
import type { RuntimeState } from '../../types/system';
import { colors } from '../../theme/tokens';

const STATE_COLOR: Record<RuntimeState, string> = {
  idle: '#8b969c',
  running: '#46c47a',
  paused: '#e0a64a',
  estopped: '#ec5a5a',
  fault: '#ec5a5a',
};

const DEPLOY_TOAST = 'Deploy (mock) started — graph would be pushed to Jetson';

export function Toolbar() {
  const state = useRuntimeStore((s) => s.state);
  const run = useRuntimeStore((s) => s.run);
  const pause = useRuntimeStore((s) => s.pause);
  const stop = useRuntimeStore((s) => s.stop);
  const estop = useRuntimeStore((s) => s.estop);
  const reset = useRuntimeStore((s) => s.reset);

  const isRecording = useSystemStore((s) => s.status.recording.value === 'On');
  const setRecording = useSystemStore((s) => s.setRecording);

  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [toastKey, setToastKey] = useState(0);

  const fileRef = useRef<HTMLInputElement | null>(null);
  const blocked = state === 'estopped' || state === 'fault';

  const onLoadFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => actions.loadProject(String(reader.result));
    reader.readAsText(file);
    e.target.value = '';
  };

  const onDeployMock = () => {
    actions.deployMock();
    setToastMessage(DEPLOY_TOAST);
    setToastKey((k) => k + 1);
  };

  return (
    <div className="toolbar">
      <div className="toolbar-brand">
        <span className="toolbar-logo" />
        <span className="toolbar-title">Rehab Robotics Studio</span>
      </div>

      <span className="toolbar-sep" />

      <button className="btn btn-run" onClick={run} disabled={blocked} title="Run / Resume">
        ▶ Run
      </button>
      <button className="btn" onClick={pause} disabled={state !== 'running'}>
        ❚❚ Pause
      </button>
      <button className="btn" onClick={stop} disabled={state === 'idle' || blocked}>
        ■ Stop
      </button>
      <button
        className={`btn${isRecording ? ' btn-rec-on' : ''}`}
        onClick={() => setRecording(!isRecording)}
        disabled={blocked}
        title="Toggle recording"
      >
        {isRecording ? '● Rec' : '○ Rec'}
      </button>

      <span className="toolbar-sep" />

      <button className="btn" onClick={() => actions.validateGraph()}>
        Validate Graph
      </button>
      <button className="btn" onClick={onDeployMock} disabled={blocked}>
        Deploy Mock
      </button>
      <button className="btn" onClick={() => actions.saveProject()}>
        Save
      </button>
      <button className="btn" onClick={() => fileRef.current?.click()}>
        Load
      </button>
      <input ref={fileRef} type="file" accept="application/json,.json" hidden onChange={onLoadFile} />

      <span className="toolbar-spacer" />

      <div className="runtime-state">
        <span className="runtime-state-label">RUNTIME</span>
        <span
          className="runtime-state-value"
          style={{ color: STATE_COLOR[state], borderColor: colors.border }}
        >
          <span className="runtime-state-dot" style={{ background: STATE_COLOR[state], boxShadow: `0 0 6px ${STATE_COLOR[state]}` }} />
          {state.toUpperCase()}
        </span>
      </div>

      {blocked ? (
        <button className="btn btn-estop btn-estop-armed" onClick={reset}>
          RESET
        </button>
      ) : (
        <button className="btn btn-estop" onClick={estop}>
          ⏻ E-STOP
        </button>
      )}

      {toastMessage != null && (
        <Toast
          key={toastKey}
          message={toastMessage}
          onDismiss={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
