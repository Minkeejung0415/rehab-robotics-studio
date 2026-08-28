/** Graph structural/type validation; extend this before allowing new connection patterns. */
import type { BlockInstance, EdgeDefinition } from '../types/blocks';
import type { LogLevel } from '../types/system';
import { getDef } from './blockDefinitions';

export interface ValidationIssue { level: LogLevel; blockId?: string; message: string; }

export function validateGraph(nodes: BlockInstance[], edges: EdgeDefinition[]): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const byId = new Map(nodes.map((node) => [node.id, node]));
  for (const edge of edges) {
    const source = byId.get(edge.sourceBlockId);
    const target = byId.get(edge.targetBlockId);
    if (!source) { issues.push({ level: 'ERROR', message: `Edge ${edge.id}: missing source block ${edge.sourceBlockId}` }); continue; }
    if (!target) { issues.push({ level: 'ERROR', message: `Edge ${edge.id}: missing target block ${edge.targetBlockId}` }); continue; }
    const sourceDefinition = getDef(source.type);
    const targetDefinition = getDef(target.type);
    if (!sourceDefinition || !targetDefinition) { issues.push({ level: 'ERROR', message: `Edge ${edge.id}: unknown block definition` }); continue; }
    const sourcePort = sourceDefinition.outputs.find((port) => port.id === edge.sourcePortId);
    const targetPort = targetDefinition.inputs.find((port) => port.id === edge.targetPortId);
    if (!sourcePort) { issues.push({ level: 'ERROR', blockId: source.id, message: `${source.name}: missing output port "${edge.sourcePortId}"` }); continue; }
    if (!targetPort) { issues.push({ level: 'ERROR', blockId: target.id, message: `${target.name}: missing input port "${edge.targetPortId}"` }); continue; }
    if (sourcePort.signalType !== targetPort.signalType) issues.push({ level: 'WARN', blockId: target.id, message: `Type mismatch on ${source.name} → ${target.name}: ${sourcePort.signalType} ≠ ${targetPort.signalType}` });
    if (targetDefinition.safeForMotorControl && !sourceDefinition.safeForMotorControl) issues.push({ level: 'SAFETY', blockId: target.id, message: `Unsafe source ${source.name} feeds motor-safe block ${target.name}` });
  }
  for (const node of nodes) {
    const definition = getDef(node.type);
    if (!definition) continue;
    for (const port of definition.inputs) {
      if (port.required === false) continue;
      if (!edges.some((edge) => edge.targetBlockId === node.id && edge.targetPortId === port.id)) issues.push({ level: 'WARN', blockId: node.id, message: `${node.name}: required input "${port.name}" is not connected` });
    }
  }
  return issues;
}
