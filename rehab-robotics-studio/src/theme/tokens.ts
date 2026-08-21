import type { SignalType } from '../types/signals';
import type { Category, BlockStatus } from '../types/blocks';
import type { IndicatorLevel } from '../types/system';

export const colors = {
  bg: '#15181a', panel: '#16191b', panel2: '#1a1f23', panel3: '#1c2226',
  border: '#23292d', borderSoft: '#262d31', grid: '#212a2e',
  textHi: '#dfe6ea', textMid: '#8b969c', textLo: '#5e686d', accent: '#4a90d6',
  good: '#46c47a', warn: '#e0a64a', fault: '#ec5a5a',
  mono: "ui-monospace, 'Cascadia Code', 'JetBrains Mono', 'SFMono-Regular', Menlo, monospace",
  sans: "'Segoe UI', system-ui, -apple-system, sans-serif",
} as const;

export const categoryColor: Record<Category, string> = {
  Sources: '#2bb89a', 'Signal Processing': '#4a90d6', Biomechanics: '#7e6fe0',
  Control: '#e0a64a', Indicators: '#3f9bd6', Recording: '#b0895a', 'User Plugins': '#a072d8',
};
export const signalColor: Record<SignalType, string> = {
  number: '#6f9bd6', bool: '#c9a23a', event: '#8a949a', force3d: '#2bb89a',
  emg_signal: '#b07ee8', imu: '#4ec0b0', motor_state: '#e0a64a',
  joint_state: '#7e6fe0', system_status: '#6f9bd6',
};
export const statusColor: Record<BlockStatus, string> = {
  idle: '#6b7378', running: '#46c47a', warning: '#e0a64a', error: '#ec5a5a',
};
export const levelColor: Record<IndicatorLevel, string> = {
  ok: '#46c47a', warn: '#e0a64a', fault: '#ec5a5a', idle: '#6b7378',
};
export function alpha(hex: string, opacity: number): string {
  const value = hex.replace('#', '');
  return `rgba(${parseInt(value.slice(0, 2), 16)}, ${parseInt(value.slice(2, 4), 16)}, ${parseInt(value.slice(4, 6), 16)}, ${opacity})`;
}
