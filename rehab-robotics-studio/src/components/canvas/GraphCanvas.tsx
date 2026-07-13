import { useMemo } from 'react';
import { getDef } from '../../graph/blockDefinitions';
import { useKeyboardDelete } from '../../hooks/useKeyboardDelete';
import { useGraphStore } from '../../state/graphStore';
import { NODE_WIDTH, Wire } from './Wire';
import { BlockNode } from './BlockNode';

const CANVAS_WIDTH = 980;
const CANVAS_HEIGHT = 720;

export function GraphCanvas() {
  const nodes = useGraphStore((s) => s.nodes);
  const edges = useGraphStore((s) => s.edges);
  const selectedId = useGraphStore((s) => s.selectedId);
  const selectedEdgeId = useGraphStore((s) => s.selectedEdgeId);
  const select = useGraphStore((s) => s.select);
  const selectEdge = useGraphStore((s) => s.selectEdge);
  const moveNode = useGraphStore((s) => s.moveNode);

  useKeyboardDelete();

  const byId = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);

  return (
    <section className="canvas-panel">
      <div className="panel-heading">BLOCK DIAGRAM</div>
      <div className="graph-canvas" onMouseDown={(event) => event.currentTarget === event.target && select(null)}>
        <svg
          className="wire-layer"
          style={{ pointerEvents: 'all' }}
          width={CANVAS_WIDTH}
          height={CANVAS_HEIGHT}
          viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`}
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
        </svg>
        {nodes.map((node) => (
          <BlockNode
            key={node.id}
            node={node}
            selected={node.id === selectedId}
            onSelect={select}
            onMove={(id, x, y) => moveNode(id, Math.max(8, Math.min(CANVAS_WIDTH - NODE_WIDTH - 8, x)), Math.max(8, Math.min(CANVAS_HEIGHT - 140, y)))}
          />
        ))}
      </div>
    </section>
  );
}
