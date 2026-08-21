import type { ParamSpec, ParamValue } from '../../types/blocks';

interface Props { spec: ParamSpec; value: ParamValue; onChange: (value: ParamValue) => void; }

export function ParamField({ spec, value, onChange }: Props) {
  const id = `param-${spec.key}`;
  if (spec.type === 'bool') return <label className="param-field param-check" htmlFor={id}><input id={id} type="checkbox" checked={Boolean(value)} onChange={(event) => onChange(event.target.checked)} /><span>{spec.label}</span></label>;
  if (spec.type === 'enum') return <label className="param-field" htmlFor={id}><span>{spec.label}</span><select id={id} value={String(value)} onChange={(event) => onChange(event.target.value)}>{spec.options?.map((option) => <option key={String(option)} value={String(option)}>{option}</option>)}</select></label>;
  if (spec.type === 'number') return <label className="param-field" htmlFor={id}><span>{spec.label}</span><div className="param-number"><input id={id} type="number" value={Number(value)} min={spec.min} max={spec.max} step={spec.step ?? 1} onChange={(event) => onChange(Number(event.target.value))} />{spec.unit && <em>{spec.unit}</em>}</div></label>;
  return <label className="param-field" htmlFor={id}><span>{spec.label}</span><input id={id} type="text" value={String(value)} onChange={(event) => onChange(event.target.value)} /></label>;
}
