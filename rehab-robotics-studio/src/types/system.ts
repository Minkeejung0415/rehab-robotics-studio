/** Shared runtime/UI status types. Runtime transitions themselves live in runtimeStore. */
export type RuntimeState = 'idle' | 'running' | 'paused' | 'estopped' | 'fault';
export type IndicatorLevel = 'ok' | 'warn' | 'fault' | 'idle';

export interface Indicator {
  label: string;
  value: string;
  level: IndicatorLevel;
}

export interface SystemStatus {
  ros: Indicator;
  jetson: Indicator;
  redPitaya: Indicator;
  motor: Indicator;
  recording: Indicator;
  fault: Indicator;
}

export type LogLevel = 'INFO' | 'WARN' | 'ERROR' | 'SAFETY';

export interface LogEntry {
  id: string;
  t: string;
  level: LogLevel;
  message: string;
}
