/** Global operator controls: run state, recording, calibration, save, and visualizer actions. */
import { useRef, useState } from 'react';
import { useRuntimeStore } from '../../state/runtimeStore';
import { useSystemStore } from '../../state/systemStore';
import { actions } from '../../state/actions';
import {
  captureOpenSimCalibration,
  clearOpenSimCalibration,
  openOpenSimVisualizer,
  setHardwareRecording,
} from '../../data/appDataSource';
import {
  createVisualizerRequestController,
  Toast,
  type VisualizerRequestController,
} from '../common/Toast';
import type { RuntimeState } from '../../types/system';
import { colors } from '../../theme/tokens';

const STATE_COLOR: Record<RuntimeState, string> = {
  idle: '#8b969c',
  running: '#46c47a',
  paused: '#e0a64a',
  estopped: '#ec5a5a',
  fault: '#ec5a5a',
};

const CALIBRATE_INSTRUCTION =
  'Stand still with knees extended, then hold while capture runs.';

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
  const [toastTone, setToastTone] = useState<'status' | 'error'>('status');
  const [toastKey, setToastKey] = useState(0);
  const [recordingBusy, setRecordingBusy] = useState(false);
  const [deployBusy, setDeployBusy] = useState(false);
  const [calibrateBusy, setCalibrateBusy] = useState(false);
  const [clearCalBusy, setClearCalBusy] = useState(false);
  const [visualizerBusy, setVisualizerBusy] = useState(false);

  const fileRef = useRef<HTMLInputElement | null>(null);
  const visualizerControllerRef = useRef<VisualizerRequestController | null>(null);
  if (visualizerControllerRef.current === null) {
    visualizerControllerRef.current = createVisualizerRequestController({
      request: openOpenSimVisualizer,
      onBusyChange: setVisualizerBusy,
      onFailure: (reason, alertMessage) => {
        useSystemStore.getState().setOpenSimVisualizerRequest({
          state: 'failed',
          reason,
        });
        setToastTone('error');
        setToastMessage(alertMessage);
        setToastKey((key) => key + 1);
      },
    });
  }
  const blocked = state === 'estopped' || state === 'fault';
  const calBusy = calibrateBusy || clearCalBusy;

  const onLoadFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => actions.loadProject(String(reader.result));
    reader.readAsText(file);
    e.target.value = '';
  };

  const onDeploy = async () => {
    if (deployBusy) return;
    setDeployBusy(true);
    const result = await actions.deployProcessingBlocks();
    setDeployBusy(false);
    setToastTone('status');
    setToastMessage(result.message);
    setToastKey((k) => k + 1);
  };

  const toggleRecording = async () => {
    if (recordingBusy) return;
    const next = !isRecording;
    setRecordingBusy(true);
    const result = await setHardwareRecording(next);
    setRecordingBusy(false);
    if (result.success) {
      setRecording(next);
      useSystemStore.getState().addLog('INFO', result.message);
      return;
    }
    useSystemStore.getState().addLog('ERROR', result.message);
    setToastTone('status');
    setToastMessage(result.message);
    setToastKey((key) => key + 1);
  };

  const onCalibrate = async () => {
    if (calBusy) return;
    setToastTone('status');
    setToastMessage(CALIBRATE_INSTRUCTION);
    setToastKey((key) => key + 1);
    useSystemStore.getState().addLog('INFO', CALIBRATE_INSTRUCTION);
    setCalibrateBusy(true);
    const result = await captureOpenSimCalibration();
    setCalibrateBusy(false);
    useSystemStore.getState().addLog(result.success ? 'INFO' : 'ERROR', result.message);
    if (!result.success) {
      setToastTone('status');
      setToastMessage(result.message);
      setToastKey((key) => key + 1);
    }
  };

  const onClearCal = async () => {
    if (calBusy) return;
    setClearCalBusy(true);
    const result = await clearOpenSimCalibration();
    setClearCalBusy(false);
    useSystemStore.getState().addLog(result.success ? 'INFO' : 'ERROR', result.message);
    setToastTone('status');
    setToastMessage(result.message);
    setToastKey((key) => key + 1);
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
        onClick={() => void toggleRecording()}
        disabled={blocked || recordingBusy || (!isRecording && state !== 'running')}
        title="Start or stop SD recording through the master ESP32"
      >
        {isRecording ? '● Rec' : '○ Rec'}
      </button>

      <span className="toolbar-sep" />

      <button className="btn" onClick={() => actions.validateGraph()}>
        Validate Graph
      </button>
      <button className="btn" onClick={() => void onDeploy()} disabled={blocked || deployBusy}>
        {deployBusy ? 'Publishing…' : 'Deploy'}
      </button>
      <button
        className="btn"
        onClick={() => void onCalibrate()}
        disabled={blocked || calBusy}
        title="Capture standing knees-extended mounting offsets"
      >
        {calibrateBusy ? 'Capturing…' : 'Calibrate'}
      </button>
      <button
        className="btn"
        onClick={() => void onClearCal()}
        disabled={blocked || calBusy}
        title="Clear OpenSim mounting-offset calibration"
      >
        {clearCalBusy ? 'Clearing…' : 'Clear cal'}
      </button>
      <button
        className="btn"
        onClick={() => void visualizerControllerRef.current?.open()}
        disabled={blocked || visualizerBusy}
        aria-busy={visualizerBusy ? 'true' : undefined}
        title="Open or show the native OpenSim 3D visualizer"
        style={{ minWidth: 112 }}
      >
        {visualizerBusy ? 'Opening…' : 'Open visualizer'}
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
          tone={toastTone}
          onDismiss={() => setToastMessage(null)}
        />
      )}
    </div>
  );
}
