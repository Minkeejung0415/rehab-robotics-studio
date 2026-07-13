import { useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent } from 'react';
import { getDef } from '../../graph/blockDefinitions';
import { useKeyboardDelete } from '../../hooks/useKeyboardDelete';
import { useGraphStore } from '../../state/graphStore';
import { useSystemStore } from '../../state/systemStore';
import type { BlockInstance, PortDefinition } from '../../types/blocks';
import { signalColor } from '../../theme/tokens';
import { ContextMenu, type ContextMenuItem } from '../common/ContextMenu';
import { NODE_WIDTH, PendingWireOverlay, portTop, Wire } from './Wire';
import { BlockNode } from './BlockNode';
import { BLOCK_TYPE_MIME } from '../library/LibraryItem';

const CANVAS_WIDTH = 980;
const CANVAS_HEIGHT = 720;

type ContextMenuState =
  | null
  | { kind: 'block' | 'wire' | 'canvas'; x: number; y: number; targetId?: string };

export function GraphCanvas() {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });
  const [isPaletteDragOver, setIsPaletteDragOver] = useState(false);
  const [contextMenu, setContextMenu] = useState<ContextMenuState>(null);
  const nodes = useGraphStore((s) => s.nodes);
  const edges = useGraphStore((s) => s.edges);
  const selectedIds = useGraphStore((s) => s.selectedIds);
  const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);
  const select = useGraphStore((s) => s.select);
  const selectEdge = useGraphStore((s) => s.selectEdge);
  const selectAll = useGraphStore((s) => s.selectAll);
  const moveNode = useGraphStore((s) => s.moveNode);
  const addNode = useGraphStore((s) => s.addNode);
  const duplicateNode = useGraphStore((s) => s.duplicateNode);
  const removeNode = useGraphStore((s) => s.removeNode);
  const removeEdge = useGraphStore((s) => s.removeEdge);
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

  const closeContextMenu = () => setContextMenu(null);

  const handleBlockContextMenu = (nodeId: string, event: MouseEvent) => {
    select(nodeId);
    setContextMenu({ kind: 'block', x: event.clientX, y: event.clientY, targetId: nodeId });
  };

  const handleWireContextMenu = (edgeId: string, event: MouseEvent) => {
    selectEdge(edgeId);
    setContextMenu({ kind: 'wire', x: event.clientX, y: event.clientY, targetId: edgeId });
  };

  const handleCanvasContextMenu = (event: MouseEvent<HTMLDivElement | SVGSVGElement>) => {
    if (event.currentTarget !== event.target) return;
    event.preventDefault();
    setContextMenu({ kind: 'canvas', x: event.clientX, y: event.clientY });
  };

  const focusBlockNameInput = () => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.getElementById('block-name-input')?.focus();
      });
    });
  };

  const contextMenuItems = useMemo((): ContextMenuItem[] => {
    if (!contextMenu) return [];
    if (contextMenu.kind === 'block' && contextMenu.targetId) {
      const targetId = contextMenu.targetId;
      return [
        {
          id: 'duplicate',
          label: 'Duplicate',
          onSelect: () => duplicateNode(targetId),
        },
        {
          id: 'rename',
          label: 'Rename',
          onSelect: () => {
            select(targetId);
            focusBlockNameInput();
          },
        },
        {
          id: 'delete',
          label: 'Delete',
          danger: true,
          separatorBefore: true,
          onSelect: () => removeNode(targetId),
        },
      ];
    }
    if (contextMenu.kind === 'wire' && contextMenu.targetId) {
      const targetId = contextMenu.targetId;
      return [
        {
          id: 'delete-wire',
          label: 'Delete',
          danger: true,
          onSelect: () => removeEdge(targetId),
        },
      ];
    }
    if (contextMenu.kind === 'canvas') {
      return [
        {
          id: 'select-all',
          label: 'Select All',
          onSelect: () => selectAll(),
        },
      ];
    }
    return [];
  }, [contextMenu, duplicateNode, removeEdge, removeNode, select, selectAll]);

  const supportsPaletteDrop = (event: DragEvent<HTMLDivElement>) => Array.from(event.dataTransfer.types).includes(BLOCK_TYPE_MIME);

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    if (!supportsPaletteDrop(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
    setIsPaletteDragOver(true);
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    if (event.currentTarget === event.target) setIsPaletteDragOver(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    if (!supportsPaletteDrop(event)) return;
    event.preventDefault();
    setIsPaletteDragOver(false);
    const type = event.dataTransfer.getData(BLOCK_TYPE_MIME);
    if (!getDef(type)) return;
    const point = toCanvasPoint(event.clientX, event.clientY);
    const x = Math.max(8, Math.min(CANVAS_WIDTH - NODE_WIDTH - 8, point.x));
    const y = Math.max(8, Math.min(CANVAS_HEIGHT - 140, point.y));
    addNode(type, x, y);
    useSystemStore.getState().addLog('INFO', `Added block: ${getDef(type)?.name ?? type}`);
  };

  return (
    <section className="canvas-panel">
      <div className="panel-heading">BLOCK DIAGRAM</div>
      <div
        ref={canvasRef}
        className={`graph-canvas${isPaletteDragOver ? ' is-palette-drop-target' : ''}`}
        onMouseDown={(event) => event.currentTarget === event.target && select(null)}
        onMouseUp={handleCanvasMouseUp}
        onMouseLeave={() => pendingWire && cancelWire()}
        onContextMenu={handleCanvasContextMenu}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <svg
          className="wire-layer"
          style={{ pointerEvents: 'all' }}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
          onMouseDown={(event) => event.currentTarget === event.target && select(null)}
          onContextMenu={handleCanvasContextMenu}
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
                onContextMenu={handleWireContextMenu}
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
            selected={selectedIds.includes(node.id)}
            onSelect={select}
            onMove={(id, x, y) => moveNode(id, Math.max(8, Math.min(CANVAS_WIDTH - NODE_WIDTH - 8, x)), Math.max(8, Math.min(CANVAS_HEIGHT - 140, y)))}
            onWireStart={handleWireStart}
            onWireFinish={handleWireFinish}
            onContextMenu={handleBlockContextMenu}
          />
        ))}
      </div>
      {contextMenu && contextMenuItems.length > 0 && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          items={contextMenuItems}
          onClose={closeContextMenu}
        />
      )}
    </section>
  );
}
