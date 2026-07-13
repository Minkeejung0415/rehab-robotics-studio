import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import { getDef } from '../../graph/blockDefinitions';
import { useKeyboardDelete } from '../../hooks/useKeyboardDelete';
import { useGraphStore } from '../../state/graphStore';
import type { BlockInstance, PortDefinition } from '../../types/blocks';
import { signalColor } from '../../theme/tokens';
import { NODE_WIDTH, PendingWireOverlay, portTop, Wire } from './Wire';
import { BlockNode } from './BlockNode';

const CANVAS_WIDTH = 980;
const CANVAS_HEIGHT = 720;

export function GraphCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });
  const nodes = useGraphStore((s) => s.nodes);
  const edges = useGraphStore((s) => s.edges);
  const selectedId = useGraphStore((s) => s.selectedId);
  const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);
  const select = useGraphStore((s) => s.select);
  const selectEdge = useGraphStore((s) => s.selectEdge);
  const moveNode = useGraphStore((s) => s.moveNode);
  const pendingWire = useGraphStore((s) => s.pendingWire);
  const startWire = useGraphStore((s) => s.startWire);
  const finishWire = useGraphStore((s) => s.finishWire);
  const cancelWire = useGraphStore((s) => s.cancelWire);

  useKeyboardDelete();

  const byId = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  const toCanvasPoint = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: clientX - rect.left + canvas.scrollLeft,
      y: clientY - rect.top + canvas.scrollTop,
    };
  };

  useEffect(() => {
    if (!pendingWire) return;

    const updatePointer = (event: globalThis.MouseEvent) => setPointer(toCanvasPoint(event.clientX, event.clientY));
    const cancelPendingWire = () => cancelWire();
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') cancelWire();
    };

    window.addEventListener('mousemove', updatePointer);
    window.addEventListener('mouseup', cancelPendingWire);
    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('mousemove', updatePointer);
      window.removeEventListener('mouseup', cancelPendingWire);
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [cancelWire, pendingWire]);

  const handleWireStart = (node: BlockInstance, port: PortDefinition, portIndex: number, event: MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    const sourceX = node.position.x + NODE_WIDTH;
    const sourceY = node.position.y + portTop(portIndex);
    setPointer(toCanvasPoint(event.clientX, event.clientY));
    startWire(node.id, port.id, port.signalType, sourceX, sourceY);
  };

  const handleWireFinish = (node: BlockInstance, port: PortDefinition, event: MouseEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (pendingWire?.signalType === port.signalType) finishWire(node.id, port.id);
    else cancelWire();
  };

  const handleCanvasMouseUp = (event: MouseEvent<HTMLDivElement>) => {
    if (event.currentTarget === event.target) cancelWire();
  };

  return (
    <section className="canvas-panel">
      <div className="panel-heading">BLOCK DIAGRAM</div>
      <div
        ref={canvasRef}
        className="graph-canvas"
        onMouseDown={(event) => event.currentTarget === event.target && select(null)}
        onMouseUp={handleCanvasMouseUp}
        onMouseLeave={() => pendingWire && cancelWire()}
      >
        <svg
          className="wire-layer"
          style={{ pointerEvents: 'all' }}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
          onMouseDown={(event) => event.currentTarget === event.target && select(null)}
        >
          {edges.map((edge) => {
            const source = byId.get(edge.sourceBlockId);
            const target = byId.get(edge.targetBlockId);
            const sourceOutputs = source ? getDef(source.type)?.outputs ?? [] : [];
            const targetInputs = target ? getDef(target.type)?.inputs ?? [] : [];
            const sourcePortIndex = sourceOutputs.findIndex((port) => port.id === edge.sourcePortId);
            const targetPortIndex = targetInputs.findIndex((port) => port.id === edge.targetPortId);
            const sourcePort = sourceOutputs[sourcePortIndex];
            const targetPort = targetInputs[targetPortIndex];
            if (!source || !target || !sourcePort || !targetPort) return null;
            return (
              <Wire
                key={edge.id}
                edge={edge}
                source={source}
                target={target}
                sourcePort={sourcePort}
                targetPort={targetPort}
                sourcePortIndex={sourcePortIndex}
                targetPortIndex={targetPortIndex}
                selected={edge.id === selectedEdgeId}
                onClick={selectEdge}
              />
            );
          })}
          {pendingWire && (
            <PendingWireOverlay
              sx={pendingWire.x}
              sy={pendingWire.y}
              tx={pointer.x}
              ty={pointer.y}
              color={signalColor[pendingWire.signalType]}
            />
          )}
        </svg>
        {nodes.map((node) => (
          <BlockNode
            key={node.id}
            node={node}
            selected={node.id === selectedId}
            onSelect={select}
            onMove={(id, x, y) => moveNode(id, Math.max(8, Math.min(CANVAS_WIDTH - NODE_WIDTH - 8, x)), Math.max(8, Math.min(CANVAS_HEIGHT - 140, y)))}
            onWireStart={handleWireStart}
            onWireFinish={handleWireFinish}
          />
        ))}
      </div>
    </section>
  );
}
