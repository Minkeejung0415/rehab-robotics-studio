import { create } from 'zustand';
import type { BlockInstance, BlockStatus, EdgeDefinition, ParamValue } from '../types/blocks';
import type { SignalType } from '../types/signals';
import { BLOCK_DEFS } from '../graph/blockDefinitions';
import { getCustomDef, defaultParamsFromDef } from './blockRegistryStore';
import { deserializeGraph, serializeGraph } from '../graph/GraphModel';
import { validateGraph, type ValidationIssue } from '../graph/validation';

export interface PendingWire {
  blockId: string;
  portId: string;
  signalType: SignalType;
  /** Canvas-relative position of the source output port dot. */
  x: number;
  y: number;
}

// Canvas geometry and persistence keys. Change these only with corresponding
// GraphCanvas behavior and migration/compatibility considerations in mind.
const NODE_WIDTH = 220;
const WORKSPACE_MAX = 10_000;
const GRAPH_ID_KEY = 'rehab-robotics:graphId';

function createGraphId(): string {
  return globalThis.crypto?.randomUUID?.() ?? `graph-${Date.now()}`;
}

function initialGraphId(): string {
  try {
    const saved = localStorage.getItem(GRAPH_ID_KEY);
    if (saved) return saved;
    const created = createGraphId();
    localStorage.setItem(GRAPH_ID_KEY, created);
    return created;
  } catch {
    return createGraphId();
  }
}

/** Build a node instance with default params from its definition. */
function makeNode(id: string, type: string, x: number, y: number): BlockInstance {
  const def = BLOCK_DEFS[type] ?? getCustomDef(type);
  return {
    id,
    type,
    name: def?.name ?? type,
    position: { x, y },
    params: def ? defaultParamsFromDef(def) : {},
    status: 'idle',
  };
}

function edge(
  id: string,
  s: string,
  sp: string,
  t: string,
  tp: string,
  signalType: EdgeDefinition['signalType'],
): EdgeDefinition {
  return { id, sourceBlockId: s, sourcePortId: sp, targetBlockId: t, targetPortId: tp, signalType };
}

/* ----- Default starter graph and saved-document compatibility ----- */

const DEFAULT_NODES: BlockInstance[] = [
  makeNode('B7', 'esp32_imu', 40, 40),
  // Keep the historical type id so saved default documents remain compatible;
  // the block now emits only the gated official OpenSim IK frame field.
  makeNode('B8', 'opensim_ik_waiting', 320, 40),
  makeNode('B9', 'joint_angle_display', 600, 40),

  makeNode('B4', 'fake_emg', 40, 340),
  makeNode('B5', 'emg_envelope', 320, 340),
  makeNode('B6', 'emg_chart', 600, 340),

  makeNode('B1', 'fake_load_cell', 40, 500),
  makeNode('B2', 'low_pass_filter', 320, 500),
  makeNode('B3', 'force_gauge', 600, 500),

  makeNode('B10', 'fake_motor_state', 40, 660),
  makeNode('B11', 'motor_state_indicator', 320, 660),
];

const DEFAULT_EDGES: EdgeDefinition[] = [
  edge('e1', 'B7', 'imu', 'B8', 'imu', 'imu'),
  edge('e2', 'B8', 'angles', 'B9', 'angle', 'joint_state'),
  edge('e3', 'B4', 'raw', 'B5', 'raw', 'emg_signal'),
  edge('e4', 'B5', 'envelope', 'B6', 'series', 'emg_signal'),
  edge('e5', 'B1', 'force', 'B2', 'in', 'force3d'),
  edge('e6', 'B2', 'out', 'B3', 'value', 'force3d'),
  edge('e7', 'B10', 'state', 'B11', 'state', 'motor_state'),
];

/** Read-only default graph document for product-path contract tests. */
export function getDefaultGraphDocument(): {
  nodes: BlockInstance[];
  edges: EdgeDefinition[];
} {
  return {
    nodes: DEFAULT_NODES.map((node) => ({
      ...node,
      position: { ...node.position },
      params: { ...node.params },
    })),
    edges: DEFAULT_EDGES.map((e) => ({ ...e })),
  };
}

interface GraphStore {
  graphId: string;
  nodes: BlockInstance[];
  edges: EdgeDefinition[];
  selectedId: string | null;
  selectedIds: string[];
  selectedEdgeId: string | null;
  pendingWire: PendingWire | null;
  validationIssues: ValidationIssue[];
  nextId: number;
  nextEdgeId: number;

  select(id: string | null): void;
  selectEdge(id: string | null): void;
  selectAll(): void;
  renameNode(nodeId: string, name: string): void;
  duplicateNode(nodeId: string): void;
  updateParam(nodeId: string, key: string, value: ParamValue): void;
  moveNode(nodeId: string, x: number, y: number): void;
  addNode(type: string, x: number, y: number): void;
  removeNode(nodeId: string): void;
  removeNodes(ids: string[]): void;
  removeEdge(edgeId: string): void;
  addEdge(sourceBlockId: string, sourcePortId: string, targetBlockId: string, targetPortId: string, signalType: SignalType): void;
  startWire(blockId: string, portId: string, signalType: SignalType, x: number, y: number): void;
  finishWire(targetBlockId: string, targetPortId: string): void;
  cancelWire(): void;
  setAllNodeStatuses(status: BlockStatus): void;

  validate(): ValidationIssue[];
  serialize(): string;
  load(json: string): void;
}

export const useGraphStore = create<GraphStore>((set, get) => ({
  graphId: initialGraphId(),
  nodes: DEFAULT_NODES,
  edges: DEFAULT_EDGES,
  selectedId: 'B1',
  selectedIds: ['B1'],
  selectedEdgeId: null,
  pendingWire: null,
  validationIssues: [],
  nextId: 12,
  nextEdgeId: 8,

  select: (id) => set({ selectedId: id, selectedIds: id ? [id] : [], selectedEdgeId: null }),

  selectEdge: (id) => set({ selectedEdgeId: id, selectedId: null, selectedIds: [] }),

  selectAll: () =>
    set((s) => {
      const ids = s.nodes.map((n) => n.id);
      const primary = s.selectedId && ids.includes(s.selectedId) ? s.selectedId : ids[0] ?? null;
      return { selectedIds: ids, selectedId: primary, selectedEdgeId: null };
    }),

  renameNode: (nodeId, name) =>
    set((s) => ({
      nodes: s.nodes.map((nd) => (nd.id === nodeId ? { ...nd, name } : nd)),
    })),

  duplicateNode: (nodeId) =>
    set((s) => {
      const src = s.nodes.find((nd) => nd.id === nodeId);
      if (!src) return s;
      const id = `B${s.nextId}`;
      const copy: BlockInstance = {
        id,
        type: src.type,
        name: `${src.name} copy`,
        position: {
          x: Math.max(8, Math.min(WORKSPACE_MAX - NODE_WIDTH - 8, src.position.x + 40)),
          y: Math.max(8, Math.min(WORKSPACE_MAX - 280, src.position.y + 40)),
        },
        params: { ...src.params },
        status: 'idle',
      };
      return {
        nodes: [...s.nodes, copy],
        nextId: s.nextId + 1,
        selectedId: id,
        selectedIds: [id],
        selectedEdgeId: null,
      };
    }),

  updateParam: (nodeId, key, value) =>
    set((s) => ({
      nodes: s.nodes.map((nd) =>
        nd.id === nodeId ? { ...nd, params: { ...nd.params, [key]: value } } : nd,
      ),
    })),

  moveNode: (nodeId, x, y) =>
    set((s) => ({
      nodes: s.nodes.map((nd) => (nd.id === nodeId ? { ...nd, position: { x, y } } : nd)),
    })),

  addNode: (type, x, y) =>
    set((s) => {
      const id = `B${s.nextId}`;
      return {
        nodes: [...s.nodes, makeNode(id, type, x, y)],
        nextId: s.nextId + 1,
        selectedId: id,
        selectedIds: [id],
        selectedEdgeId: null,
      };
    }),

  removeNode: (nodeId) =>
    set((s) => {
      const selectedIds = s.selectedIds.filter((id) => id !== nodeId);
      return {
        nodes: s.nodes.filter((nd) => nd.id !== nodeId),
        edges: s.edges.filter((e) => e.sourceBlockId !== nodeId && e.targetBlockId !== nodeId),
        selectedId: s.selectedId === nodeId ? null : s.selectedId,
        selectedIds,
      };
    }),

  removeNodes: (ids) =>
    set((s) => {
      if (ids.length === 0) return s;
      const idSet = new Set(ids);
      return {
        nodes: s.nodes.filter((nd) => !idSet.has(nd.id)),
        edges: s.edges.filter((e) => !idSet.has(e.sourceBlockId) && !idSet.has(e.targetBlockId)),
        selectedId: null,
        selectedIds: [],
        selectedEdgeId: null,
      };
    }),

  removeEdge: (edgeId) =>
    set((s) => ({
      edges: s.edges.filter((e) => e.id !== edgeId),
      selectedEdgeId: s.selectedEdgeId === edgeId ? null : s.selectedEdgeId,
    })),

  addEdge: (sourceBlockId, sourcePortId, targetBlockId, targetPortId, signalType) =>
    set((s) => {
      // Prevent duplicate connections to the same target port
      const alreadyConnected = s.edges.some(
        (e) => e.targetBlockId === targetBlockId && e.targetPortId === targetPortId,
      );
      if (alreadyConnected) return s;
      const id = `e${s.nextEdgeId}`;
      const newEdge: EdgeDefinition = { id, sourceBlockId, sourcePortId, targetBlockId, targetPortId, signalType };
      return { edges: [...s.edges, newEdge], nextEdgeId: s.nextEdgeId + 1 };
    }),

  startWire: (blockId, portId, signalType, x, y) =>
    set({
      pendingWire: { blockId, portId, signalType, x, y },
      selectedId: null,
      selectedIds: [],
      selectedEdgeId: null,
    }),

  finishWire: (targetBlockId, targetPortId) => {
    const { pendingWire } = get();
    if (!pendingWire) return;
    if (pendingWire.blockId !== targetBlockId) {
      get().addEdge(pendingWire.blockId, pendingWire.portId, targetBlockId, targetPortId, pendingWire.signalType);
    }
    set({ pendingWire: null });
  },

  cancelWire: () => set({ pendingWire: null }),

  setAllNodeStatuses: (status) =>
    set((s) => {
      if (s.nodes.length === 0) return s;
      return { nodes: s.nodes.map((n) => ({ ...n, status })) };
    }),

  validate: () => {
    const { nodes, edges } = get();
    const issues = validateGraph(nodes, edges);
    set({ validationIssues: issues });
    return issues;
  },

  serialize: () => serializeGraph(get().nodes, get().edges, get().graphId),

  load: (json) => {
    const doc = deserializeGraph(json);
    const firstId = doc.nodes[0]?.id ?? null;
    const graphId = doc.graphId || createGraphId();
    try { localStorage.setItem(GRAPH_ID_KEY, graphId); } catch { /* storage is optional */ }
    set({
      graphId,
      nodes: doc.nodes,
      edges: doc.edges,
      selectedId: firstId,
      selectedIds: firstId ? [firstId] : [],
      selectedEdgeId: null,
      validationIssues: [],
    });
  },
}));
