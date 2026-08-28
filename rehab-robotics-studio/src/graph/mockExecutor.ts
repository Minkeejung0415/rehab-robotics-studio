/** Mock graph evaluator used for Studio behavior without physical hardware. */
import type { BlockInstance, EdgeDefinition, ParamValue } from '../types/blocks';
import type { Frame, MotorState } from '../types/signals';
import { topoSort } from './GraphModel';

/** Per-node memory carried across frames (e.g. filter state). */
export type ExecMemory = Record<string, { prev: number }>;

/** Values the executor surfaces for the front-panel indicators. */
export interface ExecResult {
  force?: number;
  emg?: number;
  knee?: number;
  motor: MotorState;
}

const n = (v: ParamValue | undefined, fallback: number): number =>
  typeof v === 'number' ? v : fallback;

const clamp = (v: number, lo: number, hi: number): number => Math.max(lo, Math.min(hi, v));

/** Exponential moving average with per-node state. */
function ema(id: string, mem: ExecMemory, value: number, alpha: number): number {
  const prev = mem[id]?.prev ?? value;
  const next = prev + alpha * (value - prev);
  mem[id] = { prev: next };
  return next;
}

/**
 * Evaluate a single block. Sources read from the frame (+ their params),
 * processing/control blocks transform their inputs. Returns a map of
 * output-port id -> scalar value (the "main" signal carried on the wire).
 */
function evalBlock(
  node: BlockInstance,
  inputs: Record<string, number>,
  frame: Frame,
  mem: ExecMemory,
): Record<string, number> {
  const p = node.params;
  const t = frame.t;

  switch (node.type) {
    case 'fake_load_cell': {
      const amp = n(p.amplitude, 10);
      const f = n(p.frequency, 1);
      const noise = n(p.noise, 0.2);
      const v = amp * Math.sin(2 * Math.PI * f * t) + (Math.random() * 2 - 1) * noise * amp;
      return { out: v };
    }
    case 'fake_emg':
      return { out: frame.emg.raw };
    case 'esp32_imu':
      // Carry a stable inclination proxy from the live IMU. This preserves the
      // scalar graph contract while making downstream IK react to hardware.
      {
        const [ax, ay, az] = frame.imu.accel;
        const lateralGravity = Math.hypot(ay, az);
        const inclination = lateralGravity > 0
          ? Math.atan2(ax, lateralGravity) / (Math.PI / 2)
          : 0;
        return { imu: clamp(inclination, -1, 1) };
      }
    case 'fake_motor_state':
      return { state: frame.motor.torque };
    case 'fake_red_pitaya_stream':
      return { ch1: Math.sin(2 * Math.PI * 2 * t) };

    case 'low_pass_filter': {
      const cutoff = n(p.cutoff, 6);
      const alpha = clamp(cutoff / 50, 0.02, 0.9);
      return { out: ema(node.id, mem, inputs.in ?? 0, alpha) };
    }
    case 'gain':
      return { out: (inputs.in ?? 0) * n(p.gain, 1) };
    case 'emg_envelope': {
      const window = n(p.window, 50);
      const alpha = clamp(20 / window, 0.02, 0.9);
      return { envelope: ema(node.id, mem, Math.abs(inputs.raw ?? 0), alpha) };
    }

    case 'opensim_ik_mock': {
      const driver = inputs.imu ?? Math.sin(2 * Math.PI * 0.35 * t);
      return { angles: clamp(35 + 25 * driver, 0, 140) };
    }
    case 'opensim_ik_waiting':
      // Historical type id retained for saved graph compatibility. The default
      // product block accepts only the independently gated official IK field.
      if (
        typeof frame.openSimKneeAngleDeg === 'number'
        && Number.isFinite(frame.openSimKneeAngleDeg)
      ) {
        return { angles: frame.openSimKneeAngleDeg };
      }
      return {};
    case 'opensim_ik_live': {
      if (typeof frame.jointAngleDeg === 'number' && Number.isFinite(frame.jointAngleDeg)) {
        return { angles: frame.jointAngleDeg };
      }
      // Fail closed: do not fake a product angle of 0 when no sample is present.
      return {};
    }
    case 'joint_angle_estimator_mock': {
      const driver = inputs.imu ?? Math.sin(2 * Math.PI * 0.35 * t);
      return { angle: clamp(35 + 25 * driver, 0, 140) };
    }

    case 'safety_gate': {
      const lim = n(p.forceLimit, 80);
      return { safe: clamp(inputs.cmd ?? 0, -lim, lim) };
    }
    case 'admittance_controller_mock': {
      const d = n(p.damping, 20) || 1;
      return { target: (inputs.force ?? 0) / d };
    }
    case 'motor_command_mock':
      return { cmd: inputs.target ?? 0 };

    case 'gain_default':
    default:
      // pass-through: first input -> first output id, if any
      return {};
  }
}

/**
 * Run one execution pass over the graph for a single frame.
 * Real dataflow: values are pulled along edges in topological order.
 */
export function runMockExecutor(
  nodes: BlockInstance[],
  edges: EdgeDefinition[],
  frame: Frame,
  mem: ExecMemory,
): ExecResult {
  const order = topoSort(nodes, edges);
  const portValues: Record<string, number> = {}; // key: `${nodeId}:${portId}`

  for (const node of order) {
    const inputs: Record<string, number> = {};
    for (const e of edges) {
      if (e.targetBlockId === node.id) {
        inputs[e.targetPortId] = portValues[`${e.sourceBlockId}:${e.sourcePortId}`] ?? 0;
      }
    }
    const outs = evalBlock(node, inputs, frame, mem);
    for (const [portId, value] of Object.entries(outs)) {
      portValues[`${node.id}:${portId}`] = value;
    }
  }

  // Pull the values feeding the known indicator blocks.
  const incomingValue = (nodeId: string): number | undefined => {
    const e = edges.find((x) => x.targetBlockId === nodeId);
    return e ? portValues[`${e.sourceBlockId}:${e.sourcePortId}`] : undefined;
  };

  let force: number | undefined;
  let emg: number | undefined;
  let knee: number | undefined;
  for (const node of nodes) {
    if (node.type === 'force_gauge') force = incomingValue(node.id);
    else if (node.type === 'emg_chart') emg = incomingValue(node.id);
    else if (node.type === 'joint_angle_display') knee = incomingValue(node.id);
  }

  return { force, emg, knee, motor: frame.motor };
}
