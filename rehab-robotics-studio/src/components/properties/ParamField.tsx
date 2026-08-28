/** Typed editor for one block parameter. Validation constraints come from ParamSpec. */
import { useEffect, useState } from 'react';
import type { ParamSpec, ParamValue } from '../../types/blocks';

interface Props {
  spec: ParamSpec;
  value: ParamValue;
  onChange: (value: ParamValue) => void;
  /** Commit a numeric value only after the operator finishes editing it. */
  onCommit?: (value: number) => void;
  disabled?: boolean;
}

export function ParamField({ spec, value, onChange, onCommit, disabled = false }: Props) {
  const id = `param-${spec.key}`;
  const [numberDraft, setNumberDraft] = useState(String(value));

  useEffect(() => setNumberDraft(String(value)), [value]);

  if (spec.type === 'bool') return <label className="param-field param-check" htmlFor={id}><input id={id} type="checkbox" checked={Boolean(value)} disabled={disabled} onChange={(event) => onChange(event.target.checked)} /><span>{spec.label}</span></label>;
  if (spec.type === 'enum') return <label className="param-field" htmlFor={id}><span>{spec.label}</span><select id={id} value={String(value)} disabled={disabled} onChange={(event) => onChange(event.target.value)}>{spec.options?.map((option) => <option key={String(option)} value={String(option)}>{option}</option>)}</select></label>;
  if (spec.type === 'number') return <label className="param-field" htmlFor={id}><span>{spec.label}</span><div className="param-number"><input id={id} type="number" value={onCommit ? numberDraft : Number(value)} min={spec.min} max={spec.max} step={spec.step ?? 1} disabled={disabled} onChange={(event) => { setNumberDraft(event.target.value); if (!onCommit) onChange(Number(event.target.value)); }} onBlur={() => { if (onCommit) onCommit(Number(numberDraft)); }} onKeyDown={(event) => { if (event.key === 'Enter') event.currentTarget.blur(); if (event.key === 'Escape') setNumberDraft(String(value)); }} />{spec.unit && <em>{spec.unit}</em>}</div></label>;
  return <label className="param-field" htmlFor={id}><span>{spec.label}</span><input id={id} type="text" value={String(value)} disabled={disabled} onChange={(event) => onChange(event.target.value)} /></label>;
}
