/** Graph serialization/deserialization boundary. Preserve compatibility when changing saved fields. */
import type { BlockInstance, EdgeDefinition, BlockDefinition, GraphDocument } from '../types/blocks';
import { getDef } from './blockDefinitions';

export const NODE_W = 178;
export const HEADER_H = 30;
export const PORT_ROW_H = 22;
export const PORT_TOP = HEADER_H + 14;
export const BODY_EXTRA = 46;

export function nodeHeight(definition: BlockDefinition): number {
  return PORT_TOP + Math.max(definition.inputs.length, definition.outputs.length, 1) * PORT_ROW_H + 12 + (definition.bodyKind ? BODY_EXTRA : 0);
}
export function portY(index: number): number { return PORT_TOP + index * PORT_ROW_H + PORT_ROW_H / 2; }
export interface Point { x: number; y: number; }
export function inPortPos(node: BlockInstance, definition: BlockDefinition, portId: string): Point {
  const index = Math.max(0, definition.inputs.findIndex((port) => port.id === portId));
  return { x: node.position.x, y: node.position.y + portY(index) };
}
export function outPortPos(node: BlockInstance, definition: BlockDefinition, portId: string): Point {
  const index = Math.max(0, definition.outputs.findIndex((port) => port.id === portId));
  return { x: node.position.x + NODE_W, y: node.position.y + portY(index) };
}
export function orthPath(first: Point, second: Point): string {
  const middleX = (first.x + second.x) / 2;
  return `M ${first.x} ${first.y} L ${middleX} ${first.y} L ${middleX} ${second.y} L ${second.x} ${second.y}`;
}
export function wireLabelPos(first: Point, second: Point): Point { return { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 }; }
export function serializeGraph(nodes: BlockInstance[], edges: EdgeDefinition[], graphId?: string): string { return JSON.stringify({ version: 1, graphId, nodes, edges } satisfies GraphDocument, null, 2); }
export function deserializeGraph(json: string): GraphDocument {
  const document = JSON.parse(json) as GraphDocument;
  if (typeof document.version !== 'number' || !Array.isArray(document.nodes) || !Array.isArray(document.edges)) throw new Error('Invalid graph document');
  return document;
}
export function topoSort(nodes: BlockInstance[], edges: EdgeDefinition[]): BlockInstance[] {
  const indegree = new Map<string, number>();
  const adjacency = new Map<string, string[]>();
  nodes.forEach((node) => { indegree.set(node.id, 0); adjacency.set(node.id, []); });
  edges.forEach((edge) => {
    if (!indegree.has(edge.targetBlockId) || !indegree.has(edge.sourceBlockId)) return;
    adjacency.get(edge.sourceBlockId)!.push(edge.targetBlockId);
    indegree.set(edge.targetBlockId, (indegree.get(edge.targetBlockId) ?? 0) + 1);
  });
  const queue = nodes.filter((node) => (indegree.get(node.id) ?? 0) === 0).map((node) => node.id);
  const order: string[] = [];
  while (queue.length > 0) {
    const id = queue.shift()!;
    order.push(id);
    for (const next of adjacency.get(id) ?? []) { indegree.set(next, (indegree.get(next) ?? 0) - 1); if ((indegree.get(next) ?? 0) === 0) queue.push(next); }
  }
  if (order.length !== nodes.length) return nodes.slice();
  const byId = new Map(nodes.map((node) => [node.id, node]));
  return order.map((id) => byId.get(id)!).filter(Boolean);
}
export function defOf(node: BlockInstance): BlockDefinition | undefined { return getDef(node.type); }
