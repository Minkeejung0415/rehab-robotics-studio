import { colors } from '../../theme/tokens';

interface Props { value: number; min: number; max: number; units?: string; color?: string; width?: number; height?: number; }

export function Gauge({ value, min, max, units = '', color = colors.good, width = 150, height = 92 }: Props) {
  const fraction = Math.max(0, Math.min(1, (value - min) / (max - min || 1)));
  const theta = Math.PI * (1 - fraction);
  const centerX = width / 2;
  const centerY = height - 18;
  const radius = Math.min(width / 2 - 12, centerY - 6);
  const needleX = centerX + radius * 0.92 * Math.cos(theta);
  const needleY = centerY - radius * 0.92 * Math.sin(theta);
  const arc = (position: number) => {
    const angle = Math.PI * (1 - position);
    return { x: centerX + radius * Math.cos(angle), y: centerY - radius * Math.sin(angle) };
  };
  const start = arc(0);
  const end = arc(1);
  const current = arc(fraction);
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`}>
      <path d={`M ${start.x} ${start.y} A ${radius} ${radius} 0 0 1 ${end.x} ${end.y}`} stroke={colors.border} strokeWidth={6} fill="none" strokeLinecap="round" />
      <path d={`M ${start.x} ${start.y} A ${radius} ${radius} 0 0 1 ${current.x} ${current.y}`} stroke={color} strokeWidth={6} fill="none" strokeLinecap="round" opacity={0.55} />
      <line x1={centerX} y1={centerY} x2={needleX} y2={needleY} stroke={colors.textHi} strokeWidth={2.4} />
      <circle cx={centerX} cy={centerY} r={4} fill={colors.textHi} />
      <text x={centerX} y={height - 2} textAnchor="middle" fontSize={11} fill={colors.textLo} fontFamily={colors.mono}>{min} – {max} {units}</text>
    </svg>
  );
}
