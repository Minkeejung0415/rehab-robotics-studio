/**
 * mappingStore.ts — Zustand store for the Phase 24 Mapping Workspace
 *
 * Holds all client-side state for device-to-segment mapping, drafted assignments,
 * catalog data, and calibration interlock flag. Row identity follows D-05/D-06:
 * rows are never removed; fields are upserted from individual topic payloads.
 *
 * computeMappingStatus implements D-07 priority ordering:
 *   runtime_ready > applied > saved > draft > unassigned
 */

import { create } from 'zustand';

// ── Snapshot types (per topic payload schemas in 24-CONTEXT.md) ──────────────

export interface ModelCatalogSnapshot {
  schema?: string;
  model_hash: string;
  model_path: string;
  frame_list: Array<{ path: string; name: string }>;
}

export interface MappingCurrentSnapshot {
  schema?: string;
  revision: number;
  applied_revision: number;
  model_hash?: string;
  assignments: Record<string, { segment: string; frame: string; state: string }>;
}

export interface FleetRegistrySnapshot {
  devices: Array<{
    device_id: string;
    role?: string;
    route_state?: string;
    connection_state?: string;
    rate_hz?: number;
    drop_count?: number;
  }>;
}

export interface NCalibrationStatusSnapshot {
  state: 'capturing' | 'calibrated' | 'uncalibrated';
  revision?: number;
  model_hash?: string;
}

export interface InputValiditySnapshot {
  device_validities: Record<string, boolean>;
}

// ── Core row and store interfaces (D-04) ─────────────────────────────────────

export interface MappingRow {
  deviceId: string;
  role: string;
  connectionState: string;
  routeState: string;
  rateHz: number | null;
  dropCount: number;
  // from /rehab/mapping/current assignments:
  backendSegment: string;
  backendFrame: string;
  backendState: 'assigned' | 'not_used' | 'unassigned';
  // local draft (not yet submitted via SetAssignment):
  draftSegment: string | null;
  draftFrame: string | null;
  draftNotUsed: boolean | null;
  // computed row-level mapping status:
  mappingStatus: 'unassigned' | 'draft' | 'saved' | 'applied' | 'runtime_ready';
  // IK validity (from /rehab/opensim/input_validity):
  ikValid: boolean | null;
  // busy flag for per-row Identify:
  identifyBusy: boolean;
  identifyResult: string | null;
}

export interface MappingStore {
  rows: Record<string, MappingRow>;
  catalogModelHash: string | null;
  catalogFrameList: Array<{ path: string; name: string }>;
  catalogModelPath: string | null;
  mappingRevision: number;
  appliedRevision: number;
  mappingModelHash: string | null;
  applyStatus: 'idle' | 'applying' | 'error';
  applyError: string | null;
  calibrationInterlocked: boolean;
  // actions:
  updateFromFleetRegistry(devices: unknown[]): void;
  updateFromMappingCurrent(state: unknown): void;
  updateFromCatalog(catalog: unknown): void;
  updateInputValidity(validity: unknown): void;
  updateFromCalibrationStatus(status: unknown): void;
  setDraftSegment(deviceId: string, segment: string, frame: string): void;
  setDraftNotUsed(deviceId: string, notUsed: boolean): void;
  setIdentifyBusy(deviceId: string, busy: boolean): void;
  setIdentifyResult(deviceId: string, result: string | null): void;
  setApplyStatus(status: 'idle' | 'applying' | 'error', error?: string | null): void;
  clearDraft(deviceId: string): void;
  clearAllDrafts(): void;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function defaultRow(deviceId: string): MappingRow {
  return {
    deviceId,
    role: 'unknown',
    connectionState: 'unknown',
    routeState: 'unknown',
    rateHz: null,
    dropCount: 0,
    backendSegment: '',
    backendFrame: '',
    backendState: 'unassigned',
    draftSegment: null,
    draftFrame: null,
    draftNotUsed: null,
    mappingStatus: 'unassigned',
    ikValid: null,
    identifyBusy: false,
    identifyResult: null,
  };
}

/**
 * computeMappingStatus — pure exported function for testability.
 *
 * Priority order per D-07:
 *   runtime_ready > applied > saved > draft > unassigned
 */
export function computeMappingStatus(
  row: Pick<MappingRow, 'backendState' | 'draftSegment' | 'draftNotUsed' | 'ikValid'>,
  mappingRevision: number,
  appliedRevision: number,
): MappingRow['mappingStatus'] {
  const hasDraft = row.draftSegment !== null || row.draftNotUsed !== null;

  // Draft overrides everything when a local change is pending
  if (hasDraft) return 'draft';

  if (row.backendState === 'assigned' && appliedRevision === mappingRevision) {
    return row.ikValid === true ? 'runtime_ready' : 'applied';
  }

  if (row.backendState !== 'unassigned') return 'saved';

  return 'unassigned';
}

// ── Initial state ─────────────────────────────────────────────────────────────

const INITIAL_STATE = {
  rows: {} as Record<string, MappingRow>,
  catalogModelHash: null as string | null,
  catalogFrameList: [] as Array<{ path: string; name: string }>,
  catalogModelPath: null as string | null,
  mappingRevision: 0,
  appliedRevision: 0,
  mappingModelHash: null as string | null,
  applyStatus: 'idle' as const,
  applyError: null as string | null,
  calibrationInterlocked: false,
};

// ── Store ─────────────────────────────────────────────────────────────────────

export const useMappingStore = create<MappingStore>((set) => ({
  ...INITIAL_STATE,

  // ── updateFromFleetRegistry ─────────────────────────────────────────────
  // D-05: rows are never removed. D-06: upsert only fleet-sourced fields.
  updateFromFleetRegistry: (devices) => {
    set((s) => {
      const rows = { ...s.rows };
      for (const item of devices) {
        if (!isRecord(item) || typeof item['device_id'] !== 'string') continue;
        const deviceId = item['device_id'];
        const existing = rows[deviceId] ?? defaultRow(deviceId);
        const updated: MappingRow = {
          ...existing,
          role: typeof item['role'] === 'string' ? item['role'] : existing.role,
          connectionState: typeof item['connection_state'] === 'string' ? item['connection_state'] : existing.connectionState,
          routeState: typeof item['route_state'] === 'string' ? item['route_state'] : existing.routeState,
          rateHz: typeof item['rate_hz'] === 'number' ? item['rate_hz'] : existing.rateHz,
          dropCount: typeof item['drop_count'] === 'number' ? item['drop_count'] : existing.dropCount,
        };
        updated.mappingStatus = computeMappingStatus(updated, s.mappingRevision, s.appliedRevision);
        rows[deviceId] = updated;
      }
      return { rows };
    });
  },

  // ── updateFromMappingCurrent ────────────────────────────────────────────
  // D-06: fills in backend assignment fields; never touches draftSegment/draftFrame/draftNotUsed.
  updateFromMappingCurrent: (payload) => {
    if (
      !isRecord(payload) ||
      typeof payload['revision'] !== 'number' ||
      typeof payload['applied_revision'] !== 'number' ||
      !isRecord(payload['assignments'])
    ) {
      return; // guard: silently drop invalid payloads (T-24-02)
    }

    const newRevision = payload['revision'] as number;
    const newAppliedRevision = payload['applied_revision'] as number;
    const newModelHash = typeof payload['model_hash'] === 'string' ? payload['model_hash'] : null;
    const assignments = payload['assignments'] as Record<string, unknown>;

    set((s) => {
      const rows = { ...s.rows };
      for (const [deviceId, assignment] of Object.entries(assignments)) {
        if (!isRecord(assignment)) continue;
        const existing = rows[deviceId] ?? defaultRow(deviceId);
        const backendState = (() => {
          const st = assignment['state'];
          if (st === 'assigned' || st === 'not_used' || st === 'unassigned') return st;
          return existing.backendState;
        })();
        const updated: MappingRow = {
          ...existing,
          backendSegment: typeof assignment['segment'] === 'string' ? assignment['segment'] : existing.backendSegment,
          backendFrame: typeof assignment['frame'] === 'string' ? assignment['frame'] : existing.backendFrame,
          backendState,
          // draftSegment, draftFrame, draftNotUsed are intentionally NOT touched
        };
        updated.mappingStatus = computeMappingStatus(updated, newRevision, newAppliedRevision);
        rows[deviceId] = updated;
      }

      // Recompute status for all other rows with the new revision numbers
      for (const [deviceId, row] of Object.entries(rows)) {
        if (deviceId in assignments) continue; // already updated above
        const updated = { ...row };
        updated.mappingStatus = computeMappingStatus(updated, newRevision, newAppliedRevision);
        rows[deviceId] = updated;
      }

      return {
        rows,
        mappingRevision: newRevision,
        appliedRevision: newAppliedRevision,
        mappingModelHash: newModelHash ?? s.mappingModelHash,
      };
    });
  },

  // ── updateFromCatalog ───────────────────────────────────────────────────
  updateFromCatalog: (catalog) => {
    if (!isRecord(catalog)) return;
    set({
      catalogModelHash: typeof catalog['model_hash'] === 'string' ? catalog['model_hash'] : null,
      catalogModelPath: typeof catalog['model_path'] === 'string' ? catalog['model_path'] : null,
      catalogFrameList: Array.isArray(catalog['frame_list'])
        ? (catalog['frame_list'] as unknown[]).filter(isRecord).map((f) => ({
            path: typeof f['path'] === 'string' ? f['path'] : '',
            name: typeof f['name'] === 'string' ? f['name'] : '',
          }))
        : [],
    });
  },

  // ── updateInputValidity ─────────────────────────────────────────────────
  updateInputValidity: (validity) => {
    if (!isRecord(validity) || !isRecord(validity['device_validities'])) return;
    const deviceValidities = validity['device_validities'] as Record<string, unknown>;
    set((s) => {
      const rows = { ...s.rows };
      for (const [deviceId, valid] of Object.entries(deviceValidities)) {
        if (!(deviceId in rows)) continue;
        const existing = rows[deviceId];
        const updated: MappingRow = {
          ...existing,
          ikValid: typeof valid === 'boolean' ? valid : existing.ikValid,
        };
        updated.mappingStatus = computeMappingStatus(updated, s.mappingRevision, s.appliedRevision);
        rows[deviceId] = updated;
      }
      return { rows };
    });
  },

  // ── updateFromCalibrationStatus ─────────────────────────────────────────
  updateFromCalibrationStatus: (status) => {
    if (!isRecord(status)) return;
    const state = status['state'];
    set({ calibrationInterlocked: state === 'capturing' });
  },

  // ── setDraftSegment ─────────────────────────────────────────────────────
  setDraftSegment: (deviceId, segment, frame) => {
    set((s) => {
      if (!(deviceId in s.rows)) return s;
      const existing = s.rows[deviceId];
      const updated: MappingRow = {
        ...existing,
        draftSegment: segment,
        draftFrame: frame,
        draftNotUsed: null,
      };
      updated.mappingStatus = computeMappingStatus(updated, s.mappingRevision, s.appliedRevision);
      return { rows: { ...s.rows, [deviceId]: updated } };
    });
  },

  // ── setDraftNotUsed ─────────────────────────────────────────────────────
  // Setting draftNotUsed=true clears draftSegment in the same set() call
  setDraftNotUsed: (deviceId, notUsed) => {
    set((s) => {
      if (!(deviceId in s.rows)) return s;
      const existing = s.rows[deviceId];
      const updated: MappingRow = {
        ...existing,
        draftNotUsed: notUsed ? true : null,
        draftSegment: notUsed ? null : existing.draftSegment,
        draftFrame: notUsed ? null : existing.draftFrame,
      };
      updated.mappingStatus = computeMappingStatus(updated, s.mappingRevision, s.appliedRevision);
      return { rows: { ...s.rows, [deviceId]: updated } };
    });
  },

  // ── setIdentifyBusy ─────────────────────────────────────────────────────
  setIdentifyBusy: (deviceId, busy) => {
    set((s) => {
      if (!(deviceId in s.rows)) return s;
      return { rows: { ...s.rows, [deviceId]: { ...s.rows[deviceId], identifyBusy: busy } } };
    });
  },

  // ── setIdentifyResult ───────────────────────────────────────────────────
  // D-18: auto-clear after 5000 ms via globalThis.setTimeout (interceptable by node test mock.timers)
  setIdentifyResult: (deviceId, result) => {
    set((s) => {
      if (!(deviceId in s.rows)) return s;
      return { rows: { ...s.rows, [deviceId]: { ...s.rows[deviceId], identifyResult: result } } };
    });

    if (result !== null) {
      globalThis.setTimeout(() => {
        useMappingStore.setState((s) => {
          if (!(deviceId in s.rows)) return s;
          return { rows: { ...s.rows, [deviceId]: { ...s.rows[deviceId], identifyResult: null } } };
        });
      }, 5000);
    }
  },

  // ── setApplyStatus ──────────────────────────────────────────────────────
  setApplyStatus: (status, error = null) => {
    set({ applyStatus: status, applyError: error ?? null });
  },

  // ── clearDraft ──────────────────────────────────────────────────────────
  clearDraft: (deviceId) => {
    set((s) => {
      if (!(deviceId in s.rows)) return s;
      const existing = s.rows[deviceId];
      const updated: MappingRow = {
        ...existing,
        draftSegment: null,
        draftFrame: null,
        draftNotUsed: null,
      };
      updated.mappingStatus = computeMappingStatus(updated, s.mappingRevision, s.appliedRevision);
      return { rows: { ...s.rows, [deviceId]: updated } };
    });
  },

  // ── clearAllDrafts ──────────────────────────────────────────────────────
  clearAllDrafts: () => {
    set((s) => {
      const rows = { ...s.rows };
      for (const [deviceId, row] of Object.entries(rows)) {
        const updated: MappingRow = {
          ...row,
          draftSegment: null,
          draftFrame: null,
          draftNotUsed: null,
        };
        updated.mappingStatus = computeMappingStatus(updated, s.mappingRevision, s.appliedRevision);
        rows[deviceId] = updated;
      }
      return { rows };
    });
  },
}));
