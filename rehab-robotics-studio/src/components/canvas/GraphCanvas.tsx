/**
 * Canvas interaction layer: renders graph nodes/wires and owns drag, pan,
 * zoom, and connection gestures. Change persisted graph data in graphStore.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type MouseEvent } from 'react';
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
  const [zoom, setZoom] = useState(1.0);

  const changeZoom = useCallback((delta: number) => {
    setZoom((z) => Math.max(0.25, Math.min(2.0, Math.round((z + delta) * 10) / 10)));
  }, []);
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

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const onWheel = (e: globalThis.WheelEvent) => {
      if (!e.ctrlKey) return;
      e.preventDefault();
      changeZoom(e.deltaY < 0 ? 0.1 : -0.1);
    };
    canvas.addEventListener('wheel', onWheel, { passive: false });
    return () => canvas.removeEventListener('wheel', onWheel);
  }, [changeZoom]);

  const toCanvasPoint = (clientX: number, clientY: number) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: (clientX - rect.left + canvas.scrollLeft) / zoom,
      y: (clientY - rect.top + canvas.scrollTop) / zoom,
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

  const focusBlockNameInput = useCallback(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.getElementById('block-name-input')?.focus();
      });
    });
  }, []);

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
  }, [contextMenu, duplicateNode, focusBlockNameInput, removeEdge, removeNode, select, selectAll]);

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
      <div className="panel-heading">
        BLOCK DIAGRAM
        <div className="zoom-controls">
          <button onClick={() => changeZoom(-0.1)} title="Zoom out (Ctrl+Scroll)">−</button>
          <button className="zoom-pct" onClick={() => setZoom(1.0)} title="Reset zoom">{Math.round(zoom * 100)}%</button>
          <button onClick={() => changeZoom(0.1)} title="Zoom in (Ctrl+Scroll)">+</button>
        </div>
      </div>
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
        {/* Outer div: inflates scrollable area to match zoomed content size */}
        <div style={{ position: 'relative', width: CANVAS_WIDTH * zoom, height: CANVAS_HEIGHT * zoom, flexShrink: 0 }}>
          {/* Inner div: applies CSS scale transform */}
          <div style={{ position: 'absolute', top: 0, left: 0, width: CANVAS_WIDTH, height: CANVAS_HEIGHT, transform: `scale(${zoom})`, transformOrigin: 'top left' }}>
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
                zoom={zoom}
                selected={selectedIds.includes(node.id)}
                onSelect={select}
                onMove={(id, x, y) => moveNode(id, Math.max(8, Math.min(CANVAS_WIDTH - NODE_WIDTH - 8, x)), Math.max(8, Math.min(CANVAS_HEIGHT - 140, y)))}
                onWireStart={handleWireStart}
                onWireFinish={handleWireFinish}
                onContextMenu={handleBlockContextMenu}
              />
            ))}
          </div>
        </div>
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
