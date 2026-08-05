/**
 * MappingWorkspace.tsx — Phase 24 Mapping Workspace panel
 *
 * Reads state from useMappingStore and calls service functions via dynamic
 * imports to avoid circular dependencies with appDataSource (wired in Plan 24-04).
 *
 * Sub-component hierarchy (all in this file per UI-SPEC, file > 200 lines):
 *   MappingWorkspace
 *     MappingHeader    — panel badge, model hash/path
 *     MappingTable     — scrollable device rows
 *       MappingDeviceRow — one per device (note: avoids name collision with MappingRow type)
 *     MappingFooter    — Apply, Reset/Confirm Reset, interlock banner, apply error
 */

import { useState, useCallback, useRef } from 'react';
import type { MappingRow } from '../../state/mappingStore';
import { useMappingStore } from '../../state/mappingStore';

// ── Local style block (scoped to MappingWorkspace) ────────────────────────────

const STYLES = `
.mapping-workspace {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 0 16px;
}
.mapping-workspace-header {
  background: #16191b;
  border-bottom: 1px solid #23292d;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.mapping-table-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background: #15181a;
}
.mapping-table {
  width: 100%;
  min-width: 860px;
  border-collapse: collapse;
  font-size: 12px;
}
.mapping-table thead tr {
  background: #1a1f23;
  border-bottom: 2px solid #23292d;
  font-size: 10px;
  color: #8b969c;
  font-family: monospace;
  text-transform: uppercase;
  height: 28px;
}
.mapping-table thead th {
  padding: 4px 8px;
  text-align: left;
  position: sticky;
  top: 0;
  z-index: 2;
  background: #1a1f23;
}
.mapping-table tbody tr {
  border-bottom: 1px solid #23292d;
  background: #16191b;
  height: 40px;
  vertical-align: middle;
}
.mapping-table tbody tr:hover {
  background: #1a1f23;
}
.mapping-table td {
  padding: 4px 8px;
}
.mapping-workspace-footer {
  background: #16191b;
  border-top: 1px solid #23292d;
  padding: 10px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}
.mapping-segment-select {
  border: 1px solid #3b484e;
  background: #111416;
  color: #dfe6ea;
  padding: 3px 4px;
  width: 100%;
  font: inherit;
  font-size: 11px;
}
.mapping-segment-select:focus-visible {
  outline: 2px solid #4a90d6;
  outline-offset: -2px;
}
.mapping-segment-select:disabled {
  opacity: 0.45;
}
@media (max-width: 768px) {
  .mapping-table .mini-btn { height: 44px; padding: 0 8px; }
}
`;

// ── Helper functions ──────────────────────────────────────────────────────────

function connectionStateColor(state: string): string {
  switch (state) {
    case 'connected':     return '#46c47a';
    case 'disconnected':  return '#ec5a5a';
    case 'reconnecting':  return '#e0a64a';
    case 'offline':       return '#5e686d';
    default:              return '#8b969c';
  }
}

type PanelBadgeState = 'no_model' | 'draft' | 'saved' | 'applied' | 'runtime_ready';

function computePanelBadgeState(
  catalogModelHash: string | null,
  rows: Record<string, MappingRow>,
  mappingRevision: number,
  appliedRevision: number,
): PanelBadgeState {
  if (!catalogModelHash) return 'no_model';

  const rowList = Object.values(rows);
  if (rowList.some((r) => r.mappingStatus === 'draft')) return 'draft';

  const anyDraft = rowList.some((r) => r.draftSegment !== null || r.draftNotUsed !== null);
  if (!anyDraft && mappingRevision > appliedRevision) return 'saved';

  const assignedRows = rowList.filter((r) => r.backendState === 'assigned');
  if (appliedRevision === mappingRevision && assignedRows.length > 0) {
    const allIkValid = assignedRows.every((r) => r.ikValid === true);
    if (allIkValid) return 'runtime_ready';
    return 'applied';
  }

  return 'saved';
}

interface RowBadgeStyle {
  color: string;
  borderColor: string;
  fontWeight?: string;
  letterSpacing?: string;
}

function rowBadgeStyle(status: MappingRow['mappingStatus']): RowBadgeStyle {
  switch (status) {
    case 'draft':
      return { color: '#e0a64a', borderColor: '#e0a64a55' };
    case 'saved':
      return { color: '#4a90d6', borderColor: '#4a90d655' };
    case 'applied':
      return { color: '#46c47a', borderColor: '#46c47a55' };
    case 'runtime_ready':
      return { color: '#46c47a', borderColor: '#46c47a', fontWeight: '600', letterSpacing: '0.02em' };
    case 'unassigned':
    default:
      return { color: '#5e686d', borderColor: '#5e686d55' };
  }
}

function rowBadgeLabel(status: MappingRow['mappingStatus']): string {
  switch (status) {
    case 'draft':         return 'DRAFT';
    case 'saved':         return 'SAVED';
    case 'applied':       return 'APPLIED';
    case 'runtime_ready': return 'READY';
    case 'unassigned':
    default:              return 'UNASSIGNED';
  }
}

interface IdentifyOutcome {
  label: string;
  color: string;
}

function identifyOutcomeLabel(outcome: string): IdentifyOutcome {
  switch (outcome) {
    case 'confirmed':    return { label: 'Confirmed',   color: '#46c47a' };
    case 'timeout':      return { label: 'Timeout',     color: '#e0a64a' };
    case 'offline':      return { label: 'Offline',     color: '#5e686d' };
    case 'unsupported':  return { label: 'Unsupported', color: '#8b969c' };
    case 'rejected':     return { label: 'Rejected',    color: '#ec5a5a' };
    default:             return { label: outcome,       color: '#8b969c' };
  }
}

// ── Duplicate segment detection ───────────────────────────────────────────────

function buildDuplicateSegments(rows: Record<string, MappingRow>): Set<string> {
  const counts = new Map<string, number>();
  for (const row of Object.values(rows)) {
    const notUsedEffective = row.draftNotUsed ?? (row.backendState === 'not_used');
    if (notUsedEffective) continue;
    const effectiveSegment = row.draftSegment ?? row.backendSegment ?? null;
    if (!effectiveSegment) continue;
    counts.set(effectiveSegment, (counts.get(effectiveSegment) ?? 0) + 1);
  }
  const duplicates = new Set<string>();
  for (const [seg, count] of counts.entries()) {
    if (count > 1) duplicates.add(seg);
  }
  return duplicates;
}

// ── Per-row state (managed at parent level, keyed by deviceId) ────────────────

interface RowLocalState {
  isSaving: boolean;
  saveError: string | null;
}

// ── MappingHeader ─────────────────────────────────────────────────────────────

interface MappingHeaderProps {
  catalogModelHash: string | null;
  catalogModelPath: string | null;
  panelBadge: PanelBadgeState;
}

function MappingHeader({ catalogModelHash, catalogModelPath, panelBadge }: MappingHeaderProps) {
  function panelBadgeContent(): { label: string; className: string; style?: React.CSSProperties } {
    switch (panelBadge) {
      case 'no_model':
        return { label: 'NO MODEL', className: 'motor-pill fault' };
      case 'draft':
        return {
          label: 'DRAFT',
          className: 'motor-pill',
          style: { borderColor: '#e0a64a55', color: '#e0a64a' },
        };
      case 'saved':
        return {
          label: 'SAVED',
          className: 'motor-pill',
          style: { borderColor: '#4a90d655', color: '#4a90d6' },
        };
      case 'applied':
        return { label: 'APPLIED', className: 'motor-pill enabled' };
      case 'runtime_ready':
        return {
          label: 'RUNTIME READY',
          className: 'motor-pill',
          style: { borderColor: '#46c47a', color: '#46c47a', fontWeight: 600 },
        };
    }
  }

  const badge = panelBadgeContent();
  const hashDisplay = catalogModelHash ? catalogModelHash.slice(0, 8) : '—';
  const pathDisplay = catalogModelPath ?? '—';

  return (
    <div className="mapping-workspace-header">
      <div className="dash-head">
        <h3>Mapping Workspace</h3>
        <span
          className={badge.className}
          style={badge.style}
          role="status"
          aria-live="polite"
        >
          {badge.label}
        </span>
      </div>
      <div className="kv-grid">
        <span style={{ color: '#8b969c', fontSize: '10px' }}>Model hash</span>
        <code style={{ fontFamily: 'monospace', fontSize: '10px', color: '#dfe6ea' }}>
          {hashDisplay}
        </code>
        <span style={{ color: '#8b969c', fontSize: '10px' }}>Model path</span>
        <span style={{
          fontSize: '10px',
          color: '#dfe6ea',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          maxWidth: '320px',
        }}>
          {pathDisplay}
        </span>
      </div>
    </div>
  );
}

// ── MappingDeviceRow ──────────────────────────────────────────────────────────

interface MappingDeviceRowProps {
  row: MappingRow;
  catalogFrameList: Array<{ path: string; name: string }>;
  duplicateSegments: Set<string>;
  localState: RowLocalState;
  onSegmentChange: (deviceId: string, value: string) => void;
  onNotUsedChange: (deviceId: string, checked: boolean) => void;
  onSave: (deviceId: string) => void;
  onIdentify: (deviceId: string) => void;
}

function MappingDeviceRow({
  row,
  catalogFrameList,
  duplicateSegments,
  localState,
  onSegmentChange,
  onNotUsedChange,
  onSave,
  onIdentify,
}: MappingDeviceRowProps) {
  const {
    deviceId,
    role,
    connectionState,
    rateHz,
    dropCount,
    backendSegment,
    backendState,
    draftSegment,
    draftNotUsed,
    mappingStatus,
    identifyBusy,
    identifyResult,
  } = row;

  const notUsedEffective = draftNotUsed ?? (backendState === 'not_used');
  const effectiveSegment = notUsedEffective ? null : (draftSegment ?? backendSegment ?? null);
  const isDuplicate = effectiveSegment !== null && duplicateSegments.has(effectiveSegment);
  const hasDraft = draftSegment !== null || draftNotUsed !== null;
  const badge = rowBadgeStyle(mappingStatus);
  const badgeLabel = rowBadgeLabel(mappingStatus);
  const identifyOutcome = identifyResult !== null ? identifyOutcomeLabel(identifyResult) : null;

  const selectValue = draftSegment ?? backendSegment ?? '';
  const rateDisplay = rateHz !== null ? `${rateHz.toFixed(1)} Hz` : '—';
  const dropsDisplay = rateHz !== null ? `${dropCount} drops` : '—';

  return (
    <tr>
      {/* Column 1: MAC / device ID */}
      <td>
        <span style={{ fontFamily: 'monospace', fontSize: '12px', color: '#dfe6ea' }}>
          {deviceId}
        </span>
      </td>

      {/* Column 2: Role */}
      <td>
        <span style={{ color: '#8b969c', fontSize: '10px' }}>{role}</span>
      </td>

      {/* Column 3: Connection */}
      <td>
        <span style={{ fontFamily: 'monospace', fontSize: '10px', color: connectionStateColor(connectionState) }}>
          {connectionState}
        </span>
      </td>

      {/* Column 4: Rate / Drops */}
      <td>
        <span style={{ fontFamily: 'monospace', fontSize: '10px', color: '#8b969c' }}>
          {rateDisplay} / {dropsDisplay}
        </span>
      </td>

      {/* Column 5: Segment selector */}
      <td style={{ minWidth: '180px' }}>
        {catalogFrameList.length === 0 ? (
          <select
            className="mapping-segment-select"
            disabled
            aria-label={`Segment for device ${deviceId}`}
            value=""
            onChange={() => { /* disabled */ }}
          >
            <option value="" disabled>Model not loaded</option>
          </select>
        ) : (
          <select
            className="mapping-segment-select"
            value={selectValue}
            disabled={notUsedEffective}
            aria-label={`Segment for device ${deviceId}`}
            onChange={(e) => onSegmentChange(deviceId, e.target.value)}
          >
            <option value="">— Select segment —</option>
            {catalogFrameList.map((f) => (
              <option key={f.path} value={f.path}>{f.name}</option>
            ))}
          </select>
        )}
        {isDuplicate && (
          <span
            className="node-imu-pending"
            role="alert"
            style={{ fontSize: '10px', display: 'block', marginTop: '2px' }}
          >
            Segment already assigned to another device.
          </span>
        )}
        {localState.saveError && (
          <span
            className="health-error"
            role="alert"
            style={{ fontSize: '10px', display: 'block', marginTop: '2px' }}
          >
            {localState.saveError}
          </span>
        )}
      </td>

      {/* Column 6: Not Used checkbox */}
      <td style={{ textAlign: 'center' }}>
        <input
          type="checkbox"
          checked={notUsedEffective}
          aria-label={`Mark ${deviceId} as not used`}
          onChange={(e) => onNotUsedChange(deviceId, e.target.checked)}
        />
      </td>

      {/* Column 7: Status badge */}
      <td>
        <span
          className="status-badge"
          style={{
            color: badge.color,
            borderColor: badge.borderColor,
            fontWeight: badge.fontWeight,
            letterSpacing: badge.letterSpacing,
          }}
          role="status"
          aria-label={`${deviceId} mapping status: ${badgeLabel}`}
        >
          {badgeLabel}
          {connectionState === 'disconnected' && (
            <span style={{ color: '#5e686d', marginLeft: '4px' }}>/ Offline</span>
          )}
        </span>
      </td>

      {/* Column 8: Identify */}
      <td>
        <button
          className="mini-btn"
          disabled={identifyBusy}
          aria-label={`Identify device ${deviceId}`}
          onClick={() => onIdentify(deviceId)}
        >
          {identifyBusy ? '…' : 'Identify'}
        </button>
        {identifyOutcome !== null && (
          <span style={{ fontSize: '10px', color: identifyOutcome.color, display: 'block', marginTop: '2px' }}>
            {identifyOutcome.label}
          </span>
        )}
      </td>

      {/* Column 9: Save */}
      <td>
        <button
          className="mini-btn"
          style={hasDraft ? { borderColor: '#4a90d655' } : undefined}
          disabled={!hasDraft || localState.isSaving}
          aria-label={`Save assignment for device ${deviceId}`}
          onClick={() => onSave(deviceId)}
        >
          {localState.isSaving ? 'Saving…' : 'Save'}
        </button>
      </td>
    </tr>
  );
}

// ── MappingTable ──────────────────────────────────────────────────────────────

interface MappingTableProps {
  rows: Record<string, MappingRow>;
  catalogFrameList: Array<{ path: string; name: string }>;
  duplicateSegments: Set<string>;
  rowLocalStates: Record<string, RowLocalState>;
  onSegmentChange: (deviceId: string, value: string) => void;
  onNotUsedChange: (deviceId: string, checked: boolean) => void;
  onSave: (deviceId: string) => void;
  onIdentify: (deviceId: string) => void;
}

function MappingTable({
  rows,
  catalogFrameList,
  duplicateSegments,
  rowLocalStates,
  onSegmentChange,
  onNotUsedChange,
  onSave,
  onIdentify,
}: MappingTableProps) {
  const rowList = Object.values(rows);

  if (Object.keys(rows).length === 0) {
    return (
      <div className="mapping-table-wrap">
        <p style={{ padding: '16px', color: '#8b969c', fontSize: '12px' }}>
          No devices found — start acquisition or check ROS bridge connection.
        </p>
      </div>
    );
  }

  return (
    <div className="mapping-table-wrap">
      <table className="mapping-table" aria-label="Device segment assignments">
        <thead>
          <tr>
            <th style={{ width: '148px' }}>MAC</th>
            <th style={{ width: '72px' }}>Role</th>
            <th style={{ width: '96px' }}>Connection</th>
            <th style={{ width: '96px' }}>Rate / Drops</th>
            <th style={{ width: '180px' }}>Segment</th>
            <th style={{ width: '60px' }}>Not Used</th>
            <th style={{ width: '88px' }}>Status</th>
            <th style={{ width: '72px' }}>Identify</th>
            <th style={{ width: '56px' }}>Save</th>
          </tr>
        </thead>
        <tbody>
          {rowList.map((row) => (
            <MappingDeviceRow
              key={row.deviceId}
              row={row}
              catalogFrameList={catalogFrameList}
              duplicateSegments={duplicateSegments}
              localState={rowLocalStates[row.deviceId] ?? { isSaving: false, saveError: null }}
              onSegmentChange={onSegmentChange}
              onNotUsedChange={onNotUsedChange}
              onSave={onSave}
              onIdentify={onIdentify}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── MappingFooter ─────────────────────────────────────────────────────────────

interface MappingFooterProps {
  applyStatus: 'idle' | 'applying' | 'error';
  applyError: string | null;
  calibrationInterlocked: boolean;
  mappingRevision: number;
  catalogModelHash: string | null;
  onApply: () => void;
  onReset: () => void;
  resetConfirm: boolean;
}

function MappingFooter({
  applyStatus,
  applyError,
  calibrationInterlocked,
  mappingRevision,
  catalogModelHash,
  onApply,
  onReset,
  resetConfirm,
}: MappingFooterProps) {
  const applyEnabled =
    applyStatus !== 'applying' && !calibrationInterlocked && mappingRevision > 0;

  void catalogModelHash; // used by parent's onReset handler via closure

  return (
    <>
      {calibrationInterlocked && (
        <div
          className="node-imu-pending"
          role="status"
          aria-live="polite"
          style={{ fontSize: '12px', padding: '6px 10px', borderTop: '1px solid #23292d' }}
        >
          Apply blocked — calibration capture is active.
        </div>
      )}
      <div className="mapping-workspace-footer">
        <button
          className="btn"
          style={{ borderColor: applyEnabled ? '#4a90d6' : undefined }}
          disabled={!applyEnabled}
          aria-label="Apply mapping to runtime"
          onClick={onApply}
        >
          {applyStatus === 'applying' ? 'Applying…' : 'Apply Mapping'}
        </button>

        <button
          className="btn"
          style={resetConfirm ? { borderColor: '#ec5a5a55', color: '#ffd9d9' } : undefined}
          aria-label={resetConfirm ? 'Confirm reset all assignments' : 'Reset all assignments'}
          onClick={onReset}
        >
          {resetConfirm ? 'Confirm Reset' : 'Reset'}
        </button>

        {applyStatus === 'error' && applyError !== null && (
          <span
            className="health-error"
            role="alert"
            aria-live="assertive"
            style={{ fontSize: '12px', alignSelf: 'center' }}
          >
            {applyError}
          </span>
        )}
      </div>
    </>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

export function MappingWorkspace() {
  // Store selectors
  const rows = useMappingStore((s) => s.rows);
  const catalogModelHash = useMappingStore((s) => s.catalogModelHash);
  const catalogModelPath = useMappingStore((s) => s.catalogModelPath);
  const catalogFrameList = useMappingStore((s) => s.catalogFrameList);
  const mappingRevision = useMappingStore((s) => s.mappingRevision);
  const appliedRevision = useMappingStore((s) => s.appliedRevision);
  const applyStatus = useMappingStore((s) => s.applyStatus);
  const applyError = useMappingStore((s) => s.applyError);
  const calibrationInterlocked = useMappingStore((s) => s.calibrationInterlocked);

  // Per-row local UI state (isSaving, saveError) keyed by deviceId
  const [rowLocalStates, setRowLocalStates] = useState<Record<string, RowLocalState>>({});

  // Reset two-click confirmation state
  const [resetConfirm, setResetConfirm] = useState(false);
  const resetTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const confirmResetBtnRef = useRef<HTMLButtonElement | null>(null);

  // ── Panel badge ──────────────────────────────────────────────────────────
  const panelBadge = computePanelBadgeState(
    catalogModelHash,
    rows,
    mappingRevision,
    appliedRevision,
  );

  // ── Duplicate segment detection (D-21) ───────────────────────────────────
  const duplicateSegments = buildDuplicateSegments(rows);

  // ── Segment selector change handler (D-16) ───────────────────────────────
  const handleSegmentChange = useCallback((deviceId: string, value: string) => {
    useMappingStore.getState().setDraftSegment(deviceId, value, value);
  }, []);

  // ── Not Used checkbox change handler (D-16) ──────────────────────────────
  const handleNotUsedChange = useCallback((deviceId: string, checked: boolean) => {
    useMappingStore.getState().setDraftNotUsed(deviceId, checked);
  }, []);

  // ── Per-row Save handler (D-13, D-14) ────────────────────────────────────
  const handleSave = useCallback(async (deviceId: string) => {
    const store = useMappingStore.getState();
    const row = store.rows[deviceId];
    if (!row) return;

    setRowLocalStates((prev) => ({
      ...prev,
      [deviceId]: { isSaving: true, saveError: null },
    }));

    try {
      // @ts-expect-error — callMappingSetAssignment is wired in Plan 24-04
      const { callMappingSetAssignment } = await import('../../data/appDataSource');
      const segment = row.draftSegment ?? row.backendSegment ?? '';
      const frame = row.draftFrame ?? row.backendFrame ?? segment;
      const state = row.draftNotUsed ? 'not_used' : 'assigned';
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      const result = await (callMappingSetAssignment as (
        deviceId: string,
        segment: string,
        frame: string,
        state: string,
      ) => Promise<{ outcome: string; detail?: string }>)(deviceId, segment, frame, state);

      if (result.outcome === 'ok') {
        useMappingStore.getState().clearDraft(deviceId);
        setRowLocalStates((prev) => ({
          ...prev,
          [deviceId]: { isSaving: false, saveError: null },
        }));
      } else {
        setRowLocalStates((prev) => ({
          ...prev,
          [deviceId]: {
            isSaving: false,
            saveError: `Save failed: ${result.detail ?? result.outcome}`,
          },
        }));
      }
    } catch (err) {
      setRowLocalStates((prev) => ({
        ...prev,
        [deviceId]: {
          isSaving: false,
          saveError: `Save failed: ${String(err)}`,
        },
      }));
    }
  }, []);

  // ── Per-row Identify handler (D-17, D-18) ────────────────────────────────
  const handleIdentify = useCallback(async (deviceId: string) => {
    useMappingStore.getState().setIdentifyBusy(deviceId, true);
    try {
      // @ts-expect-error — callMappingIdentifyDevice is wired in Plan 24-04
      const { callMappingIdentifyDevice } = await import('../../data/appDataSource');
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      const result = await (callMappingIdentifyDevice as (
        deviceId: string,
      ) => Promise<{ outcome: string }>)(deviceId);
      useMappingStore.getState().setIdentifyResult(deviceId, result.outcome);
    } catch {
      useMappingStore.getState().setIdentifyResult(deviceId, 'error');
    } finally {
      useMappingStore.getState().setIdentifyBusy(deviceId, false);
    }
  }, []);

  // ── Apply Mapping handler (D-15) ─────────────────────────────────────────
  const handleApply = useCallback(async () => {
    const store = useMappingStore.getState();
    store.setApplyStatus('applying');
    try {
      // @ts-expect-error — callMappingApply is wired in Plan 24-04
      const { callMappingApply } = await import('../../data/appDataSource');
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      const result = await (callMappingApply as (
        expectedRevision: number,
      ) => Promise<{ outcome: string; detail?: string; applied_revision?: number }>)(
        store.mappingRevision,
      );

      const outcome = result.outcome;
      if (outcome === 'applied') {
        useMappingStore.getState().setApplyStatus('idle');
        useMappingStore.getState().clearAllDrafts();
      } else if (outcome === 'stale_revision') {
        useMappingStore.getState().setApplyStatus(
          'error',
          'Mapping changed since last refresh. Reload and retry.',
        );
      } else if (outcome === 'recording_active') {
        useMappingStore.getState().setApplyStatus(
          'error',
          'Cannot apply while recording is active. Stop recording first.',
        );
      } else if (outcome === 'calibration_active') {
        useMappingStore.getState().setApplyStatus(
          'error',
          'Cannot apply during calibration capture. Wait for calibration to complete.',
        );
      } else {
        useMappingStore.getState().setApplyStatus(
          'error',
          result.detail ? `Apply failed: ${result.detail}` : 'Apply failed — check ROS connection.',
        );
      }
    } catch (err) {
      useMappingStore.getState().setApplyStatus(
        'error',
        `Apply failed: ${String(err)}`,
      );
    }
  }, []);

  // ── Reset handler (D-15, T-24-09) ────────────────────────────────────────
  const handleReset = useCallback(async () => {
    if (!resetConfirm) {
      // First click: arm the confirmation state
      if (resetTimeoutRef.current !== null) clearTimeout(resetTimeoutRef.current);
      setResetConfirm(true);
      resetTimeoutRef.current = setTimeout(() => {
        setResetConfirm(false);
        resetTimeoutRef.current = null;
      }, 5000);
      // Focus Confirm Reset button programmatically (keyboard nav per UI-SPEC)
      // Small delay to let React re-render
      setTimeout(() => {
        confirmResetBtnRef.current?.focus();
      }, 0);
      return;
    }

    // Second click: execute reset
    if (resetTimeoutRef.current !== null) {
      clearTimeout(resetTimeoutRef.current);
      resetTimeoutRef.current = null;
    }
    setResetConfirm(false);

    try {
      // @ts-expect-error — callMappingReset is wired in Plan 24-04
      const { callMappingReset } = await import('../../data/appDataSource');
      const currentHash = useMappingStore.getState().catalogModelHash;
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      await (callMappingReset as (modelHash: string | null) => Promise<{ outcome: string }>)(
        currentHash,
      );
      // Backend re-publishes /rehab/mapping/current; store updates automatically
    } catch (err) {
      useMappingStore.getState().setApplyStatus(
        'error',
        `Reset failed: ${String(err)}`,
      );
    }
  }, [resetConfirm]);

  // ── Empty model state ────────────────────────────────────────────────────
  if (!catalogModelHash && Object.keys(rows).length === 0) {
    return (
      <>
        <style>{STYLES}</style>
        <div className="mapping-workspace dash-panel">
          <MappingHeader
            catalogModelHash={catalogModelHash}
            catalogModelPath={catalogModelPath}
            panelBadge={panelBadge}
          />
          <p style={{ padding: '16px', color: '#8b969c', fontSize: '12px' }}>
            No model loaded — connect to ROS and load an .osim file to begin.
          </p>
        </div>
      </>
    );
  }

  return (
    <>
      <style>{STYLES}</style>
      <div className="mapping-workspace dash-panel">
        <MappingHeader
          catalogModelHash={catalogModelHash}
          catalogModelPath={catalogModelPath}
          panelBadge={panelBadge}
        />

        <MappingTable
          rows={rows}
          catalogFrameList={catalogFrameList}
          duplicateSegments={duplicateSegments}
          rowLocalStates={rowLocalStates}
          onSegmentChange={handleSegmentChange}
          onNotUsedChange={handleNotUsedChange}
          onSave={(id) => void handleSave(id)}
          onIdentify={(id) => void handleIdentify(id)}
        />

        <MappingFooter
          applyStatus={applyStatus}
          applyError={applyError}
          calibrationInterlocked={calibrationInterlocked}
          mappingRevision={mappingRevision}
          catalogModelHash={catalogModelHash}
          onApply={() => void handleApply()}
          onReset={() => void handleReset()}
          resetConfirm={resetConfirm}
        />
      </div>
    </>
  );
}
