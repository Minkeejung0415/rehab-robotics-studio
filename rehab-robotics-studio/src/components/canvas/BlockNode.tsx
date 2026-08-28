/** Renders and edits one graph block. Hardware parameter changes route through appDataSource. */
import { useEffect, useState, type MouseEvent } from 'react';
import type { BlockInstance, PortDefinition } from '../../types/blocks';
import { getDef } from '../../graph/blockDefinitions';
import { categoryColor, signalColor, statusColor } from '../../theme/tokens';
import { useSignals } from '../../hooks/useSignals';
import { Gauge } from '../common/Gauge';
import { MiniChart } from '../common/MiniChart';
import { Port } from './Port';
import { NODE_HEADER_HEIGHT, NODE_WIDTH, PORT_ROW_HEIGHT, portTop } from './Wire';
import { useGraphStore } from '../../state/graphStore';
import { useRuntimeStore } from '../../state/runtimeStore';
import { useSystemStore } from '../../state/systemStore';
import { setHardwareImuControl } from '../../data/appDataSource';
import { formatLiveKneeAngle } from '../../data/liveKneeAngle';
import type { ImuControlParameter } from '../../data/RosbridgeDataSource';

interface Props {
  node: BlockInstance;
  zoom: number;
  selected: boolean;
  onSelect: (id: string) => void;
  onMove: (id: string, x: number, y: number) => void;
  onWireStart: (node: BlockInstance, port: PortDefinition, portIndex: number, event: MouseEvent<HTMLDivElement>) => void;
  onWireFinish: (node: BlockInstance, port: PortDefinition, event: MouseEvent<HTMLDivElement>) => void;
  onContextMenu?: (nodeId: string, event: MouseEvent) => void;
}

function NodeBody({ kind }: { kind?: string }) {
  const signals = useSignals();
  if (kind === 'gauge') {
    return <Gauge value={signals.forceProcessed} min={-50} max={50} units="N" height={70} />;
  }
  if (kind === 'chart') {
    return <MiniChart data={signals.emgSeries} color={signalColor.emg_signal} height={50} />;
  }
  if (kind === 'angle') {
    const kneeDisplay = formatLiveKneeAngle(signals.kneeAngle);
    return (
      <div
        className={`node-readout knee-angle-readout ${kneeDisplay.isLive ? 'is-live' : 'is-unavailable'}`}
        data-state={kneeDisplay.isLive ? 'live' : 'unavailable'}
      >
        <span className="knee-angle-value">{kneeDisplay.valueText}</span>
        {kneeDisplay.statusText && (
          <span className="knee-angle-status">{kneeDisplay.statusText}</span>
        )}
      </div>
    );
  }
  if (kind === 'motor') {
    return (
      <div className="node-metrics">
        <span>pos {signals.motor.position.toFixed(2)}</span>
        <span>vel {signals.motor.velocity.toFixed(2)}</span>
        <span>tau {signals.motor.torque.toFixed(2)}</span>
      </div>
    );
  }
  return null;
}

function ImuConfigurationControl({ node }: { node: BlockInstance }) {
  const updateParam = useGraphStore((state) => state.updateParam);
  const setSampleRate = useRuntimeStore((state) => state.setSampleRate);
  const [pendingKey, setPendingKey] = useState<string | null>(null);
  const rate = Number(node.params.sampleRate ?? 100);
  const effectiveRate = Number(node.params.effectiveSampleRate ?? rate);
  const accelRange = Number(node.params.accelRangeG ?? String(node.params.range ?? '2g').replace('g', '')) || 2;
  const gyroRange = Number(node.params.gyroRangeDps ?? 250);
  const filterEnabled = node.params.filterEnabled !== false;
  const [draftRate, setDraftRate] = useState(String(rate));
  const [draftEffectiveRate, setDraftEffectiveRate] = useState(String(effectiveRate));

  useEffect(() => setDraftRate(String(rate)), [rate]);
  useEffect(() => setDraftEffectiveRate(String(effectiveRate)), [effectiveRate]);

  const changeControl = async (
    pending: string,
    parameter: ImuControlParameter,
    value: number | boolean,
    graphKey: string,
  ) => {
    const isRateControl = parameter === 'sample_rate_hz' || parameter === 'effective_sample_rate_hz';
    setPendingKey(pending);
    const result = await setHardwareImuControl(parameter, value);
    setPendingKey(null);
    if (result.success && isRateControl) {
      // A Pair Rate is not applied until bridge + firmware acknowledge it.
      // Keeping both fields at the confirmed value prevents a cosmetic GUI
      // change from being mistaken for an ESP32 configuration change.
      if (parameter === 'sample_rate_hz') {
        updateParam(node.id, 'sampleRate', value);
        setSampleRate(Number(value));
      }
      updateParam(node.id, 'effectiveSampleRate', value);
    } else if (result.success) {
      updateParam(node.id, graphKey, value);
    } else if (parameter === 'sample_rate_hz') {
      setDraftRate(String(rate));
    } else if (parameter === 'effective_sample_rate_hz') {
      setDraftEffectiveRate(String(effectiveRate));
    }
    useSystemStore.getState().addLog(result.success ? 'INFO' : 'ERROR', result.message);
  };

  const applyRate = (draft: string, current: number, parameter: ImuControlParameter, graphKey: string) => {
    const nextRate = Number(draft);
    if (Number.isInteger(nextRate) && nextRate >= 1 && nextRate <= 1000 && nextRate !== current) {
      void changeControl(graphKey, parameter, nextRate, graphKey);
    } else if (parameter === 'sample_rate_hz') {
      setDraftRate(String(current));
    } else {
      setDraftEffectiveRate(String(current));
    }
  };

  return (
    <div className="node-imu-controls" onMouseDown={(event) => event.stopPropagation()}>
      <label><span>PAIR RATE</span><input aria-label="ESP32 pair sample rate" type="number" min={1} max={1000} step={1} value={draftRate} disabled={pendingKey !== null} onChange={(event) => setDraftRate(event.target.value)} onBlur={() => applyRate(draftRate, rate, 'sample_rate_hz', 'sampleRate')} onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur(); if (event.key === 'Escape') setDraftRate(String(rate)); }} /><b>Hz</b></label>
      <label><span>FILTER</span><select aria-label="ESP32 filter" value={filterEnabled ? 'on' : 'off'} disabled={pendingKey !== null} onChange={(event) => void changeControl('filterEnabled', 'filter_enabled', event.target.value === 'on', 'filterEnabled')}><option value="on">ON</option><option value="off">OFF</option></select></label>
      <label><span>ACCEL</span><select aria-label="ESP32 accelerometer range" value={accelRange} disabled={pendingKey !== null} onChange={(event) => void changeControl('accelRangeG', 'accel_range_g', Number(event.target.value), 'accelRangeG')}>{[2, 4, 8, 16].map((value) => <option key={value} value={value}>{value} g</option>)}</select></label>
      <label><span>GYRO</span><select aria-label="ESP32 gyroscope range" value={gyroRange} disabled={pendingKey !== null} onChange={(event) => void changeControl('gyroRangeDps', 'gyro_range_dps', Number(event.target.value), 'gyroRangeDps')}>{[250, 500, 1000, 2000].map((value) => <option key={value} value={value}>{value} dps</option>)}</select></label>
      <label><span>EFFECTIVE</span><input aria-label="ESP32 effective sample rate" type="number" value={draftEffectiveRate} readOnly /><b>Hz</b></label>
      {pendingKey && <em className="node-imu-pending">APPLYING</em>}
    </div>
  );
}

export function BlockNode({ node, zoom, selected, onSelect, onMove, onWireStart, onWireFinish, onContextMenu }: Props) {
  const def = getDef(node.type);
  const inputCount = def?.inputs.length ?? 0;
  const outputCount = def?.outputs.length ?? 0;
  const portRows = Math.max(inputCount, outputCount, 1);
  const hasImuControls = node.type === 'esp32_imu';
  const bodyRows = def?.bodyKind === 'angle' ? 94 : def?.bodyKind ? 78 : hasImuControls ? 180 : 30;
  const height = NODE_HEADER_HEIGHT + 22 + portRows * PORT_ROW_HEIGHT + bodyRows;
  const accent = def ? categoryColor[def.category] : '#8b969c';

  const startDrag = (event: MouseEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    onSelect(node.id);
    const startX = event.clientX;
    const startY = event.clientY;
    const origin = node.position;

    const onPointerMove = (moveEvent: globalThis.MouseEvent) => {
      onMove(node.id, origin.x + (moveEvent.clientX - startX) / zoom, origin.y + (moveEvent.clientY - startY) / zoom);
    };
    const onPointerUp = () => {
      window.removeEventListener('mousemove', onPointerMove);
      window.removeEventListener('mouseup', onPointerUp);
    };

    window.addEventListener('mousemove', onPointerMove);
    window.addEventListener('mouseup', onPointerUp);
  };

  return (
    <div
      className={`block-node${selected ? ' is-selected' : ''}`}
      style={{ left: node.position.x, top: node.position.y, width: NODE_WIDTH, minHeight: height }}
      onMouseDown={startDrag}
      role="button"
      tabIndex={0}
      onClick={() => onSelect(node.id)}
      onContextMenu={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onContextMenu?.(node.id, event);
      }}
    >
      <div className="block-header" style={{ borderTopColor: accent }}>
        <div>
          <div className="block-name">{node.name}</div>
          <div className="block-type">{node.type}</div>
        </div>
        <span className="block-id">{node.id}</span>
      </div>

      <div className="block-meta">
        <span className="runtime-badge">{def?.runtime ?? 'unknown'}</span>
        <span className="status-badge" style={{ color: statusColor[node.status] }}>
          {node.status}
        </span>
      </div>

      <div className="port-layer" style={{ height: Math.max(30, portRows * PORT_ROW_HEIGHT + 18) }}>
        {def?.inputs.map((port, index) => (
          <Port
            key={port.id}
            port={port}
            top={portTop(index) - NODE_HEADER_HEIGHT - 26}
            onWireFinish={(input, event) => onWireFinish(node, input, event)}
          />
        ))}
        {def?.outputs.map((port, index) => (
          <Port
            key={port.id}
            port={port}
            top={portTop(index) - NODE_HEADER_HEIGHT - 26}
            onWireStart={(output, event) => onWireStart(node, output, index, event)}
          />
        ))}
      </div>

      <div className="block-io-summary">
        <span>IN {inputCount}</span>
        <span>OUT {outputCount}</span>
      </div>
      {hasImuControls && <ImuConfigurationControl node={node} />}
      <NodeBody kind={def?.bodyKind} />
    </div>
  );
}
