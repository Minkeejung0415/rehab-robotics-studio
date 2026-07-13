import type { MouseEvent } from 'react';
import type { BlockInstance, PortDefinition } from '../../types/blocks';
import { getDef } from '../../graph/blockDefinitions';
import { categoryColor, signalColor, statusColor } from '../../theme/tokens';
import { useSignals } from '../../hooks/useSignals';
import { Gauge } from '../common/Gauge';
import { MiniChart } from '../common/MiniChart';
import { Port } from './Port';
import { NODE_HEADER_HEIGHT, NODE_WIDTH, PORT_ROW_HEIGHT, portTop } from './Wire';

interface Props {
  node: BlockInstance;
  selected: boolean;
  onSelect: (id: string) => void;
  onMove: (id: string, x: number, y: number) => void;
  onWireStart: (node: BlockInstance, port: PortDefinition, portIndex: number, event: MouseEvent<HTMLDivElement>) => void;
  onWireFinish: (node: BlockInstance, port: PortDefinition, event: MouseEvent<HTMLDivElement>) => void;
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
    return <div className="node-readout">{signals.kneeAngle.toFixed(1)} deg</div>;
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

export function BlockNode({ node, selected, onSelect, onMove, onWireStart, onWireFinish }: Props) {
  const def = getDef(node.type);
  const inputCount = def?.inputs.length ?? 0;
  const outputCount = def?.outputs.length ?? 0;
  const portRows = Math.max(inputCount, outputCount, 1);
  const bodyRows = def?.bodyKind ? 78 : 30;
  const height = NODE_HEADER_HEIGHT + 22 + portRows * PORT_ROW_HEIGHT + bodyRows;
  const accent = def ? categoryColor[def.category] : '#8b969c';

  const startDrag = (event: MouseEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    onSelect(node.id);
    const startX = event.clientX;
    const startY = event.clientY;
    const origin = node.position;

    const onPointerMove = (moveEvent: globalThis.MouseEvent) => {
      onMove(node.id, origin.x + moveEvent.clientX - startX, origin.y + moveEvent.clientY - startY);
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
      <NodeBody kind={def?.bodyKind} />
    </div>
  );
}
