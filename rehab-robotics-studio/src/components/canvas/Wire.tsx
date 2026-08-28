/** Draws a graph connection. Change graph edges in graphStore, not this presentation component. */
import type { MouseEvent } from 'react';
import type { BlockInstance, EdgeDefinition, PortDefinition } from '../../types/blocks';
import { signalColor } from '../../theme/tokens';

export const NODE_WIDTH = 220;
export const NODE_HEADER_HEIGHT = 34;
export const PORT_ROW_HEIGHT = 22;

export function portTop(index: number): number {
  return NODE_HEADER_HEIGHT + 18 + index * PORT_ROW_HEIGHT;
}

interface Props {
  edge: EdgeDefinition;
  source: BlockInstance;
  target: BlockInstance;
  sourcePort: PortDefinition;
  targetPort: PortDefinition;
  sourcePortIndex: number;
  targetPortIndex: number;
  selected?: boolean;
  onClick?: (edgeId: string) => void;
  onContextMenu?: (edgeId: string, event: MouseEvent) => void;
}

export function Wire({ edge, source, target, sourcePortIndex, targetPortIndex, selected, onClick, onContextMenu }: Props) {
  const sx = source.position.x + NODE_WIDTH;
  const sy = source.position.y + portTop(sourcePortIndex);
  const tx = target.position.x;
  const ty = target.position.y + portTop(targetPortIndex);
  const dx = Math.max(70, Math.abs(tx - sx) * 0.45);
  const path = `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
  const color = selected ? '#4a90d6' : signalColor[edge.signalType];

  return (
    <g
      className={`wire${selected ? ' wire-selected' : ''}`}
      data-edge-id={edge.id}
      onClick={(e) => { e.stopPropagation(); onClick?.(edge.id); }}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onContextMenu?.(edge.id, e);
      }}
    >
      <path className="wire-hit" d={path} />
      <path className="wire-line" d={path} stroke={color} strokeWidth={selected ? 2.8 : 2.2} />
      {!selected && (
        <text className="wire-label" x={(sx + tx) / 2} y={(sy + ty) / 2 - 6} fill={color}>
          {edge.signalType}
        </text>
      )}
    </g>
  );
}

interface PendingProps {
  sx: number;
  sy: number;
  tx: number;
  ty: number;
  color: string;
}

/** Dashed preview wire drawn while the user is mid-connection. */
export function PendingWireOverlay({ sx, sy, tx, ty, color }: PendingProps) {
  const dx = Math.max(70, Math.abs(tx - sx) * 0.45);
  const path = `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
  return (
    <path
      d={path}
      stroke={color}
      strokeWidth={2.2}
      fill="none"
      strokeDasharray="7 4"
      opacity={0.75}
      style={{ pointerEvents: 'none' }}
    />
  );
}
