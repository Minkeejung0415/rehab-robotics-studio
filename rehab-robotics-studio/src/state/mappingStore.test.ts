/**
 * 24-01: Vitest-style unit tests for mappingStore.ts using node:test runner
 *
 * Tests:
 *   1. updateFromFleetRegistry creates rows keyed by deviceId
 *   2. updateFromFleetRegistry with empty array leaves existing rows intact (D-05)
 *   3. updateFromMappingCurrent sets backend fields without clearing draftSegment (D-06)
 *   4. updateFromCatalog sets catalog fields
 *   5. updateInputValidity sets ikValid per device
 *   6. computeMappingStatus: runtime_ready when assigned, rev match, ikValid=true (D-07)
 *   7. computeMappingStatus: applied when assigned, rev match, ikValid=false
 *   8. computeMappingStatus: saved when not unassigned, no draft, rev not applied
 *   9. computeMappingStatus: draft when draftSegment set
 *   10. computeMappingStatus: draft when draftNotUsed set
 *   11. computeMappingStatus: unassigned when backendState=unassigned, no draft
 *   12. setDraftSegment sets draftSegment + draftFrame
 *   13. setDraftNotUsed(true) sets draftNotUsed=true AND draftSegment=null
 *   14. clearDraft removes draftSegment, draftFrame, draftNotUsed for one device
 *   15. clearAllDrafts removes draft fields for all devices
 *   16. setApplyStatus sets applyStatus and applyError
 *   17. updateFromCalibrationStatus capturing → calibrationInterlocked=true; calibrated → false
 *   18. setIdentifyResult sets identifyResult; auto-clears after 5000 ms (fake timers)
 */

import assert from 'node:assert/strict';
import { describe, it, before, beforeEach, after } from 'node:test';
import { mock } from 'node:test';

import { useMappingStore, computeMappingStatus } from './mappingStore.js';
import type { MappingRow } from './mappingStore.js';

// ── Helpers ───────────────────────────────────────────────────────────────────

const DEVICE_A = 'esp32:aabbccddeeff';
const DEVICE_B = 'esp32:001122334455';

function resetStore(): void {
  useMappingStore.setState({
    rows: {},
    catalogModelHash: null,
    catalogFrameList: [],
    catalogModelPath: null,
    mappingRevision: 0,
    appliedRevision: 0,
    mappingModelHash: null,
    applyStatus: 'idle',
    applyError: null,
    calibrationInterlocked: false,
  });
}

function getRow(deviceId: string): MappingRow {
  const row = useMappingStore.getState().rows[deviceId];
  assert.ok(row, `Row for ${deviceId} should exist`);
  return row;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('mappingStore — 24-01', () => {
  beforeEach(() => {
    resetStore();
  });

  // ── Test 1: updateFromFleetRegistry creates rows ──────────────────────────
  it('01 updateFromFleetRegistry creates one row keyed by deviceId', () => {
    useMappingStore.getState().updateFromFleetRegistry([
      {
        device_id: DEVICE_A,
        role: 'master',
        route_state: 'active',
        connection_state: 'connected',
        rate_hz: 100,
        drop_count: 0,
      },
    ]);

    const state = useMappingStore.getState();
    assert.ok(DEVICE_A in state.rows, 'row for DEVICE_A should exist');
    const row = state.rows[DEVICE_A];
    assert.equal(row.deviceId, DEVICE_A);
    assert.equal(row.role, 'master');
    assert.equal(row.connectionState, 'connected');
    assert.equal(row.routeState, 'active');
    assert.equal(row.rateHz, 100);
    assert.equal(row.dropCount, 0);
  });

  // ── Test 2: updateFromFleetRegistry with empty array leaves rows intact ────
  it('02 updateFromFleetRegistry with empty array leaves existing rows (D-05)', () => {
    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);

    // Now call with empty — row must remain
    useMappingStore.getState().updateFromFleetRegistry([]);

    const state = useMappingStore.getState();
    assert.ok(DEVICE_A in state.rows, 'DEVICE_A row must not be removed when registry sends empty list');
  });

  // ── Test 3: updateFromMappingCurrent sets backend fields; draft unchanged ──
  it('03 updateFromMappingCurrent sets backendSegment without clearing draftSegment', () => {
    // Create row first
    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);

    // Set a draft
    useMappingStore.getState().setDraftSegment(DEVICE_A, 'tibia', 'tibia/frame');

    // Now update from mapping/current
    useMappingStore.getState().updateFromMappingCurrent({
      schema: 'rehab.mapping_current.1',
      revision: 5,
      applied_revision: 3,
      model_hash: 'abc123',
      assignments: {
        [DEVICE_A]: { segment: 'femur', frame: 'femur/frame', state: 'assigned' },
      },
    });

    const row = getRow(DEVICE_A);
    assert.equal(row.backendSegment, 'femur');
    assert.equal(row.backendFrame, 'femur/frame');
    assert.equal(row.backendState, 'assigned');
    // Draft must NOT be cleared
    assert.equal(row.draftSegment, 'tibia', 'draftSegment must not be cleared by updateFromMappingCurrent');
    assert.equal(row.draftFrame, 'tibia/frame', 'draftFrame must not be cleared');

    const store = useMappingStore.getState();
    assert.equal(store.mappingRevision, 5);
    assert.equal(store.appliedRevision, 3);
    assert.equal(store.mappingModelHash, 'abc123');
  });

  // ── Test 4: updateFromCatalog sets catalog fields ─────────────────────────
  it('04 updateFromCatalog sets catalogModelHash, catalogModelPath, catalogFrameList', () => {
    useMappingStore.getState().updateFromCatalog({
      schema: 'rehab.model_catalog.1',
      model_hash: 'hash42',
      model_path: '/models/knee.osim',
      frame_list: [
        { path: 'femur_r', name: 'Femur Right' },
        { path: 'tibia_r', name: 'Tibia Right' },
      ],
    });

    const state = useMappingStore.getState();
    assert.equal(state.catalogModelHash, 'hash42');
    assert.equal(state.catalogModelPath, '/models/knee.osim');
    assert.equal(state.catalogFrameList.length, 2);
    assert.equal(state.catalogFrameList[0].path, 'femur_r');
    assert.equal(state.catalogFrameList[1].name, 'Tibia Right');
  });

  // ── Test 5: updateInputValidity sets ikValid per device ───────────────────
  it('05 updateInputValidity sets ikValid on matching rows', () => {
    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
      { device_id: DEVICE_B, role: 'slave', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);

    useMappingStore.getState().updateInputValidity({
      device_validities: { [DEVICE_A]: true, [DEVICE_B]: false },
    });

    assert.equal(getRow(DEVICE_A).ikValid, true);
    assert.equal(getRow(DEVICE_B).ikValid, false);
  });

  // ── Test 6: computeMappingStatus runtime_ready (D-07) ────────────────────
  it('06 computeMappingStatus runtime_ready: assigned, revs match, ikValid=true', () => {
    const row: Pick<MappingRow, 'backendState' | 'draftSegment' | 'draftNotUsed' | 'ikValid'> = {
      backendState: 'assigned',
      draftSegment: null,
      draftNotUsed: null,
      ikValid: true,
    };
    const status = computeMappingStatus(row, 7, 7);
    assert.equal(status, 'runtime_ready');
  });

  // ── Test 7: computeMappingStatus applied ─────────────────────────────────
  it('07 computeMappingStatus applied: assigned, revs match, ikValid=false', () => {
    const row: Pick<MappingRow, 'backendState' | 'draftSegment' | 'draftNotUsed' | 'ikValid'> = {
      backendState: 'assigned',
      draftSegment: null,
      draftNotUsed: null,
      ikValid: false,
    };
    const status = computeMappingStatus(row, 7, 7);
    assert.equal(status, 'applied');
  });

  // ── Test 8: computeMappingStatus saved ───────────────────────────────────
  it('08 computeMappingStatus saved: assigned, appliedRevision < mappingRevision, no draft', () => {
    const row: Pick<MappingRow, 'backendState' | 'draftSegment' | 'draftNotUsed' | 'ikValid'> = {
      backendState: 'assigned',
      draftSegment: null,
      draftNotUsed: null,
      ikValid: null,
    };
    const status = computeMappingStatus(row, 7, 3);
    assert.equal(status, 'saved');
  });

  // ── Test 9: computeMappingStatus draft (draftSegment set) ────────────────
  it('09 computeMappingStatus draft: draftSegment set overrides backendState', () => {
    const row: Pick<MappingRow, 'backendState' | 'draftSegment' | 'draftNotUsed' | 'ikValid'> = {
      backendState: 'unassigned',
      draftSegment: 'tibia',
      draftNotUsed: null,
      ikValid: null,
    };
    const status = computeMappingStatus(row, 7, 7);
    assert.equal(status, 'draft');
  });

  // ── Test 10: computeMappingStatus draft (draftNotUsed set) ───────────────
  it('10 computeMappingStatus draft: draftNotUsed=true is draft state', () => {
    const row: Pick<MappingRow, 'backendState' | 'draftSegment' | 'draftNotUsed' | 'ikValid'> = {
      backendState: 'assigned',
      draftSegment: null,
      draftNotUsed: true,
      ikValid: null,
    };
    const status = computeMappingStatus(row, 7, 7);
    assert.equal(status, 'draft');
  });

  // ── Test 11: computeMappingStatus unassigned ──────────────────────────────
  it('11 computeMappingStatus unassigned: backendState=unassigned, no draft', () => {
    const row: Pick<MappingRow, 'backendState' | 'draftSegment' | 'draftNotUsed' | 'ikValid'> = {
      backendState: 'unassigned',
      draftSegment: null,
      draftNotUsed: null,
      ikValid: null,
    };
    const status = computeMappingStatus(row, 0, 0);
    assert.equal(status, 'unassigned');
  });

  // ── Test 12: setDraftSegment ──────────────────────────────────────────────
  it('12 setDraftSegment sets draftSegment and draftFrame', () => {
    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);

    useMappingStore.getState().setDraftSegment(DEVICE_A, 'femur', 'femur/frame');

    const row = getRow(DEVICE_A);
    assert.equal(row.draftSegment, 'femur');
    assert.equal(row.draftFrame, 'femur/frame');
    assert.equal(row.mappingStatus, 'draft');
  });

  // ── Test 13: setDraftNotUsed(true) clears draftSegment ───────────────────
  it('13 setDraftNotUsed(true) sets draftNotUsed=true AND draftSegment=null', () => {
    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);
    useMappingStore.getState().setDraftSegment(DEVICE_A, 'tibia', 'tibia/frame');
    useMappingStore.getState().setDraftNotUsed(DEVICE_A, true);

    const row = getRow(DEVICE_A);
    assert.equal(row.draftNotUsed, true);
    assert.equal(row.draftSegment, null, 'draftSegment must be cleared when draftNotUsed=true');
    assert.equal(row.mappingStatus, 'draft');
  });

  // ── Test 14: clearDraft removes draft fields for one device ───────────────
  it('14 clearDraft removes draftSegment, draftFrame, draftNotUsed for one device', () => {
    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
      { device_id: DEVICE_B, role: 'slave', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);
    useMappingStore.getState().setDraftSegment(DEVICE_A, 'tibia', 'tibia/frame');
    useMappingStore.getState().setDraftSegment(DEVICE_B, 'femur', 'femur/frame');

    useMappingStore.getState().clearDraft(DEVICE_A);

    const rowA = getRow(DEVICE_A);
    assert.equal(rowA.draftSegment, null);
    assert.equal(rowA.draftFrame, null);
    assert.equal(rowA.draftNotUsed, null);

    // DEVICE_B draft must remain
    const rowB = getRow(DEVICE_B);
    assert.equal(rowB.draftSegment, 'femur', 'DEVICE_B draft must be untouched');
  });

  // ── Test 15: clearAllDrafts removes draft fields for all devices ──────────
  it('15 clearAllDrafts removes draft fields for all devices', () => {
    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
      { device_id: DEVICE_B, role: 'slave', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);
    useMappingStore.getState().setDraftSegment(DEVICE_A, 'tibia', 'tibia/frame');
    useMappingStore.getState().setDraftSegment(DEVICE_B, 'femur', 'femur/frame');

    useMappingStore.getState().clearAllDrafts();

    const rowA = getRow(DEVICE_A);
    const rowB = getRow(DEVICE_B);
    assert.equal(rowA.draftSegment, null);
    assert.equal(rowA.draftFrame, null);
    assert.equal(rowA.draftNotUsed, null);
    assert.equal(rowB.draftSegment, null);
    assert.equal(rowB.draftFrame, null);
    assert.equal(rowB.draftNotUsed, null);
  });

  // ── Test 16: setApplyStatus ───────────────────────────────────────────────
  it('16 setApplyStatus(error, message) sets applyStatus=error and applyError', () => {
    useMappingStore.getState().setApplyStatus('error', 'some error');

    const state = useMappingStore.getState();
    assert.equal(state.applyStatus, 'error');
    assert.equal(state.applyError, 'some error');
  });

  // ── Test 17: updateFromCalibrationStatus sets calibrationInterlocked ──────
  it('17 updateFromCalibrationStatus capturing → interlocked; calibrated → false', () => {
    useMappingStore.getState().updateFromCalibrationStatus({ state: 'capturing', revision: 1, model_hash: 'h1' });
    assert.equal(useMappingStore.getState().calibrationInterlocked, true);

    useMappingStore.getState().updateFromCalibrationStatus({ state: 'calibrated', revision: 1, model_hash: 'h1' });
    assert.equal(useMappingStore.getState().calibrationInterlocked, false);
  });

  // ── Test 18: setIdentifyResult auto-clears after 5000 ms (fake timers) ────
  it('18 setIdentifyResult sets identifyResult; auto-clears after 5000 ms', (t) => {
    mock.timers.enable({ apis: ['setTimeout'] });

    useMappingStore.getState().updateFromFleetRegistry([
      { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 },
    ]);

    useMappingStore.getState().setIdentifyResult(DEVICE_A, 'LED flashing');
    assert.equal(getRow(DEVICE_A).identifyResult, 'LED flashing', 'identifyResult should be set immediately');

    // Advance timers by 5001 ms — the store schedules a 5000 ms auto-clear
    mock.timers.tick(5001);

    assert.equal(getRow(DEVICE_A).identifyResult, null, 'identifyResult should be null after 5001 ms');

    mock.timers.reset();
  });

  // ── Test 19 (bonus): updateFromFleetRegistry upserts without duplicating ──
  it('19 updateFromFleetRegistry calling twice does not duplicate rows', () => {
    const device = { device_id: DEVICE_A, role: 'master', route_state: 'active', connection_state: 'connected', rate_hz: 100, drop_count: 0 };
    useMappingStore.getState().updateFromFleetRegistry([device]);
    useMappingStore.getState().updateFromFleetRegistry([device]);

    const state = useMappingStore.getState();
    assert.equal(Object.keys(state.rows).length, 1, 'only one row should exist after two identical calls');
  });

  // ── Test 20 (bonus): updateFromMappingCurrent guard: invalid payload no-ops ─
  it('20 updateFromMappingCurrent with invalid payload does not change state', () => {
    const before = useMappingStore.getState().mappingRevision;

    useMappingStore.getState().updateFromMappingCurrent(null);
    useMappingStore.getState().updateFromMappingCurrent('bad string');
    useMappingStore.getState().updateFromMappingCurrent({ revision: 'not-a-number' });

    assert.equal(useMappingStore.getState().mappingRevision, before, 'revision must not change on invalid payload');
  });
});
