import type { IndicatorLevel } from '../../types/system';
import { levelColor } from '../../theme/tokens';

interface Props {
  label: string;
  value: string;
  level: IndicatorLevel;
}

export function StatusLight({ label, value, level }: Props) {
  const color = levelColor[level];
  return (
    <div className="status-light">
      <span className="status-light-dot" style={{ background: color, boxShadow: `0 0 6px ${color}` }} />
      <span className="status-light-label">{label}:</span>
      <span className="status-light-value" style={{ color }}>{value}</span>
    </div>
  );
}
