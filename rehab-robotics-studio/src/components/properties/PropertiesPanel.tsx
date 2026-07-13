import { useEffect, useRef } from 'react';
import { getDef } from '../../graph/blockDefinitions';
import { useGraphStore } from '../../state/graphStore';
import { signalColor } from '../../theme/tokens';
import { ParamField } from './ParamField';

export function PropertiesPanel() {
  const selectedId = useGraphStore((s) => s.selectedId);
  const node = useGraphStore((s) => s.nodes.find((item) => item.id === s.selectedId));
  const issues = useGraphStore((s) => s.validationIssues.filter((issue) => !selectedId || issue.blockId === selectedId));
  const updateParam = useGraphStore((s) => s.updateParam);
  const renameNode = useGraphStore((s) => s.renameNode);
  const def = node ? getDef(node.type) : undefined;
  const lastNonEmptyRef = useRef(node?.name ?? '');

  useEffect(() => {
    if (node && node.name.trim() !== '') {
      lastNonEmptyRef.current = node.name;
    }
  }, [node?.id, node?.name]);

  return (
    <aside className="properties">
      <div className="panel-heading">PROPERTIES</div>
      {!node || !def ? (
        <div className="empty-panel">Select a block to inspect its parameters and terminal contract.</div>
      ) : (
        <div className="properties-scroll">
          <section className="prop-section">
            <label className="param-field" htmlFor="block-name-input">
              <span>Name</span>
              <input
                id="block-name-input"
                type="text"
                value={node.name}
                onChange={(event) => {
                  const next = event.target.value;
                  renameNode(node.id, next);
                  if (next.trim() !== '') lastNonEmptyRef.current = next;
                }}
                onBlur={() => {
                  if (node.name.trim() === '') {
                    renameNode(node.id, lastNonEmptyRef.current);
                  }
                }}
              />
            </label>
            <div className="kv-grid">
              <span>ID</span>
              <strong>{node.id}</strong>
              <span>Type</span>
              <strong>{node.type}</strong>
              <span>Runtime</span>
              <strong>{def.runtime}</strong>
              <span>Status</span>
              <strong>{node.status}</strong>
              <span>Motor Safe</span>
              <strong>{def.safeForMotorControl ? 'Yes' : 'No'}</strong>
            </div>
          </section>

          <section className="prop-section">
            <h3>Inputs</h3>
            {def.inputs.length === 0 ? <div className="muted">No inputs</div> : def.inputs.map((port) => (
              <div key={port.id} className="port-row">
                <span>{port.name}</span>
                <em style={{ color: signalColor[port.signalType] }}>{port.signalType}</em>
                {port.required !== false && <b>req</b>}
              </div>
            ))}
          </section>

          <section className="prop-section">
            <h3>Outputs</h3>
            {def.outputs.length === 0 ? <div className="muted">No outputs</div> : def.outputs.map((port) => (
              <div key={port.id} className="port-row">
                <span>{port.name}</span>
                <em style={{ color: signalColor[port.signalType] }}>{port.signalType}</em>
              </div>
            ))}
          </section>

          <section className="prop-section">
            <h3>Parameters</h3>
            {def.params.length === 0 ? <div className="muted">No editable parameters</div> : def.params.map((param) => (
              <ParamField
                key={param.key}
                spec={param}
                value={node.params[param.key] ?? param.default}
                onChange={(value) => updateParam(node.id, param.key, value)}
              />
            ))}
          </section>

          <section className="prop-section">
            <h3>Validation</h3>
            {issues.length === 0 ? (
              <div className="validation-ok">No validation issues for this selection.</div>
            ) : (
              issues.map((issue, index) => (
                <div key={`${issue.message}-${index}`} className={`validation-msg level-${issue.level.toLowerCase()}`}>
                  <strong>{issue.level}</strong>
                  <span>{issue.message}</span>
                </div>
              ))
            )}
          </section>
        </div>
      )}
    </aside>
  );
}
