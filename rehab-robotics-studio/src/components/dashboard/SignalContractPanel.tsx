/** Displays accepted/rejected canonical signal-contract traffic for diagnostics. */
import { useState } from 'react';
import { MiniChart } from '../common/MiniChart';
import type { CanonicalSignalRejectionState, SignalSnapshot } from '../../data/signalBus';
import type {
  CanonicalSignalRejectionReason,
  CanonicalSignalSample,
  SignalAvailabilityReason,
} from '../../types/signals';

export type SignalUnitMode = 'raw' | 'si';
export type SignalAvailabilityBadge = 'AVAILABLE' | 'RAW ONLY' | 'UNAVAILABLE' | 'INVALID';

export interface ChannelValuePresentation {
  readonly label: string;
  readonly value: string;
}

export interface ChannelPresentation {
  readonly key: 'accel' | 'gyro' | 'magnetometer' | 'quaternion';
  readonly label: string;
  readonly badge: SignalAvailabilityBadge;
  readonly unit: 'counts' | 'm/s²' | 'rad/s' | 'µT' | 'unitless' | null;
  readonly values: readonly ChannelValuePresentation[];
  readonly reason: string | null;
}

const AVAILABILITY_REASON_COPY: Readonly<Record<SignalAvailabilityReason, string>> = {
  capability_absent: 'source capability not declared',
  config_invalid: 'sensor sensitivity is invalid',
  calibration_missing: 'calibration provenance is missing',
  calibration_invalid: 'calibration provenance is invalid',
  stale: 'sample is stale',
  missing: 'value is missing',
  malformed: 'value is malformed',
  non_finite: 'value is not finite',
  zero_norm: 'quaternion norm is zero',
  norm_out_of_range: 'quaternion norm is outside the valid range',
};

const REJECTION_REASON_COPY: Readonly<Record<CanonicalSignalRejectionReason, string>> = {
  schema_invalid: 'Canonical schema is invalid',
  device_id_invalid: 'Canonical full MAC is invalid',
  topic_device_mismatch: 'Topic identity does not match the canonical full MAC',
  sequence_invalid: 'Sample sequence is invalid',
  sequence_origin_invalid: 'Sample sequence origin is invalid',
  acquisition_time_invalid: 'Acquisition time metadata is invalid',
  bridge_time_invalid: 'Bridge monotonic time is invalid',
  reconnect_epoch_invalid: 'Reconnect epoch is invalid',
  mapping_epoch_invalid: 'Mapping provenance epoch is invalid',
  capability_invalid: 'Source capability metadata is invalid',
  raw_field_missing: 'A required raw channel is missing',
  raw_field_invalid: 'A raw channel value is invalid',
  raw_field_out_of_range: 'A raw channel value is outside the signed count range',
  conversion_invalid: 'Validated conversion metadata is invalid',
  quaternion_invalid: 'Quaternion validity metadata is invalid',
  applied_mapping_invalid: 'Applied mapping provenance is invalid',
};

export function availabilityReasonText(reason: SignalAvailabilityReason): string {
  return AVAILABILITY_REASON_COPY[reason];
}

export function rejectionReasonText(reason: CanonicalSignalRejectionReason): string {
  return REJECTION_REASON_COPY[reason];
}

function displayNumber(value: number): string {
  return String(value);
}

function unavailableValues(labels: readonly string[]): readonly ChannelValuePresentation[] {
  return labels.map((label) => ({ label, value: '—' }));
}

function rawValues(
  labels: readonly string[],
  values: readonly number[],
): readonly ChannelValuePresentation[] {
  return labels.map((label, index) => ({ label, value: displayNumber(values[index]!) }));
}

function siUnavailableReason(reason: SignalAvailabilityReason): string {
  return `SI unavailable — ${availabilityReasonText(reason)}. Raw counts remain available.`;
}

export function buildChannelPresentation(
  sample: CanonicalSignalSample,
  mode: SignalUnitMode,
): readonly ChannelPresentation[] {
  const accelLabels = ['ax', 'ay', 'az'] as const;
  const gyroLabels = ['gx', 'gy', 'gz'] as const;
  const magLabels = ['mx', 'my', 'mz'] as const;
  const quaternionLabels = ['qw', 'qx', 'qy', 'qz'] as const;

  const vectorRow = (
    key: 'accel' | 'gyro',
    label: string,
    labels: readonly string[],
    raw: readonly number[],
  ): ChannelPresentation => {
    const si = sample.si[key];
    if (mode === 'raw') {
      return {
        key,
        label,
        badge: si.available ? 'AVAILABLE' : 'RAW ONLY',
        unit: 'counts',
        values: rawValues(labels, raw),
        reason: si.available ? null : siUnavailableReason(si.reason),
      };
    }
    if (!si.available) {
      return {
        key,
        label,
        badge: 'RAW ONLY',
        unit: null,
        values: unavailableValues(labels),
        reason: siUnavailableReason(si.reason),
      };
    }
    return {
      key,
      label,
      badge: 'AVAILABLE',
      unit: key === 'accel' ? 'm/s²' : 'rad/s',
      values: rawValues(labels, [si.values.x, si.values.y, si.values.z]),
      reason: null,
    };
  };

  let magnetometer: ChannelPresentation;
  if (!sample.capabilities.magnetometer) {
    magnetometer = {
      key: 'magnetometer',
      label: 'Magnetic field',
      badge: 'UNAVAILABLE',
      unit: null,
      values: unavailableValues(magLabels),
      reason: 'Magnetometer unavailable — source capability not declared.',
    };
  } else if (mode === 'raw') {
    magnetometer = {
      key: 'magnetometer',
      label: 'Magnetic field',
      badge: sample.si.magnetometer.available ? 'AVAILABLE' : 'RAW ONLY',
      unit: 'counts',
      values: rawValues(magLabels, [sample.raw.mx, sample.raw.my, sample.raw.mz]),
      reason: sample.si.magnetometer.available
        ? null
        : siUnavailableReason(sample.si.magnetometer.reason),
    };
  } else if (!sample.si.magnetometer.available) {
    magnetometer = {
      key: 'magnetometer',
      label: 'Magnetic field',
      badge: 'RAW ONLY',
      unit: null,
      values: unavailableValues(magLabels),
      reason: siUnavailableReason(sample.si.magnetometer.reason),
    };
  } else {
    magnetometer = {
      key: 'magnetometer',
      label: 'Magnetic field',
      badge: 'AVAILABLE',
      unit: 'µT',
      values: rawValues(magLabels, [
        sample.si.magnetometer.values.x,
        sample.si.magnetometer.values.y,
        sample.si.magnetometer.values.z,
      ]),
      reason: null,
    };
  }

  let quaternion: ChannelPresentation;
  if (!sample.capabilities.quaternion) {
    quaternion = {
      key: 'quaternion',
      label: 'Quaternion',
      badge: 'UNAVAILABLE',
      unit: null,
      values: unavailableValues(quaternionLabels),
      reason: 'Quaternion unavailable — source capability not declared.',
    };
  } else if (!sample.quaternion.available) {
    quaternion = {
      key: 'quaternion',
      label: 'Quaternion',
      badge: 'INVALID',
      unit: null,
      values: unavailableValues(quaternionLabels),
      reason: `Quaternion invalid — ${availabilityReasonText(sample.quaternion.reason)}. No orientation value is displayed.`,
    };
  } else {
    quaternion = {
      key: 'quaternion',
      label: 'Quaternion',
      badge: 'AVAILABLE',
      unit: 'unitless',
      values: rawValues(quaternionLabels, sample.quaternion.values),
      reason: null,
    };
  }

  return [
    vectorRow('accel', 'Acceleration', accelLabels, [sample.raw.ax, sample.raw.ay, sample.raw.az]),
    vectorRow('gyro', 'Angular rate', gyroLabels, [sample.raw.gx, sample.raw.gy, sample.raw.gz]),
    magnetometer,
    quaternion,
  ];
}

function safeMacId(deviceId: string): string {
  return deviceId.replace(/[^a-zA-Z0-9_-]/g, '-');
}

function mappingText(sample: CanonicalSignalSample): string {
  const { revision, segment, frame } = sample.applied_mapping;
  return segment !== null && frame !== null
    ? `Applied r${revision} · ${segment} / ${frame}`
    : `Applied r${revision} · Unassigned`;
}

function mappingAccessibleText(sample: CanonicalSignalSample): string {
  const { revision, segment, frame } = sample.applied_mapping;
  return segment !== null && frame !== null
    ? `Authoritative applied mapping revision ${revision}, segment ${segment}, frame ${frame}`
    : `Authoritative applied mapping revision ${revision}, unassigned`;
}

function validityReasonCodes(sample: CanonicalSignalSample): string {
  return [
    `accel: ${sample.si.accel.available ? 'available' : sample.si.accel.reason}`,
    `gyro: ${sample.si.gyro.available ? 'available' : sample.si.gyro.reason}`,
    `magnetometer: ${sample.si.magnetometer.available ? 'available' : sample.si.magnetometer.reason}`,
    `quaternion: ${sample.quaternion.available ? 'available' : sample.quaternion.reason}`,
  ].join(', ');
}

function capabilitiesText(sample: CanonicalSignalSample): string {
  return Object.entries(sample.capabilities)
    .map(([name, declared]) => `${name}: ${declared ? 'declared' : 'absent'}`)
    .join(', ');
}

function badgeClass(badge: SignalAvailabilityBadge): string {
  if (badge === 'AVAILABLE') return 'signal-availability--available';
  if (badge === 'RAW ONLY') return 'signal-availability--raw-only';
  if (badge === 'INVALID') return 'signal-availability--invalid';
  return 'signal-availability--unavailable';
}

const TRACE_COLORS = ['#4a90d6', '#46c47a', '#e0a64a', '#b78cff'] as const;

function channelSeries(
  history: readonly CanonicalSignalSample[],
  mode: SignalUnitMode,
  channelKey: ChannelPresentation['key'],
  valueLabel: string,
): number[] {
  const series: number[] = [];
  for (const historicalSample of history) {
    const channel = buildChannelPresentation(historicalSample, mode)
      .find((candidate) => candidate.key === channelKey);
    const value = channel?.values.find((candidate) => candidate.label === valueLabel)?.value;
    if (value === undefined || value === '—') continue;
    const numeric = Number(value);
    if (Number.isFinite(numeric)) series.push(numeric);
  }
  return series;
}

function ChannelRow({
  row,
  sourceId,
  history,
  unitMode,
}: {
  row: ChannelPresentation;
  sourceId: string;
  history: readonly CanonicalSignalSample[];
  unitMode: SignalUnitMode;
}) {
  const reasonId = row.reason ? `${sourceId}-${row.key}-reason` : undefined;
  return (
    <div className="signal-channel-row" aria-describedby={reasonId}>
      <div className="signal-channel-group">
        <strong>{row.label}</strong>
        <span className={`status-badge signal-availability ${badgeClass(row.badge)}`}>
          {row.badge}
        </span>
      </div>
      <div className="signal-channel-values">
        {row.values.map((value) => (
          <span className="signal-channel-value" key={value.label}>
            <span>{value.label}</span>
            <strong className={value.value === '—' ? 'signal-value--unavailable' : undefined}>
              {value.value}
            </strong>
          </span>
        ))}
      </div>
      <div className="signal-channel-availability">
        {row.unit !== null && <span className="signal-channel-unit">{row.unit}</span>}
        {row.reason !== null && <span id={reasonId} className="signal-channel-reason">{row.reason}</span>}
      </div>
      <div className="signal-channel-graphs">
        {row.values.map((value, index) => (
          <div className="signal-component-graph" key={value.label}>
            <span>{value.label}</span>
            <MiniChart
              data={channelSeries(history, unitMode, row.key, value.label)}
              color={TRACE_COLORS[index % TRACE_COLORS.length]!}
              height={48}
              fill={false}
              ariaLabel={`${value.label} history for ${sourceId}`}
            />
          </div>
        ))}
      </div>
    </div>
  );
}

interface RejectionNoticeProps {
  readonly rejection: CanonicalSignalRejectionState;
  readonly hasAcceptedSample: boolean;
}

function RejectionNotice({ rejection, hasAcceptedSample }: RejectionNoticeProps) {
  const reason = rejectionReasonText(rejection.reason);
  return (
    <div
      className="validation-msg signal-rejection"
      role={rejection.should_announce ? 'alert' : 'status'}
    >
      <strong>{hasAcceptedSample ? 'Last update rejected' : 'Sample rejected'}</strong>
      <span>
        {reason}. Values were not displayed. Check the source contract and ROS connection.
      </span>
      <span className="signal-rejection-time">
        Rejected at {new Date(rejection.rejected_at_ms).toISOString()}
      </span>
    </div>
  );
}

export interface SignalSourceCardProps {
  readonly sample: CanonicalSignalSample;
  readonly rejection?: CanonicalSignalRejectionState;
  readonly history?: readonly CanonicalSignalSample[];
  readonly initialUnitMode?: SignalUnitMode;
  readonly initialProvenanceOpen?: boolean;
}

export function SignalSourceCard({
  sample,
  rejection,
  history,
  initialUnitMode = 'raw',
  initialProvenanceOpen = false,
}: SignalSourceCardProps) {
  const safeId = safeMacId(sample.device_id);
  const sourceId = `signal-source-${safeId}`;
  const siDisabledId = `signal-si-disabled-${safeId}`;
  const provenanceId = `signal-provenance-${safeId}`;
  const siAvailable = sample.si.accel.available
    || sample.si.gyro.available
    || sample.si.magnetometer.available;
  const [unitMode, setUnitMode] = useState<SignalUnitMode>(
    initialUnitMode === 'si' && !siAvailable ? 'raw' : initialUnitMode,
  );
  const [provenanceOpen, setProvenanceOpen] = useState(initialProvenanceOpen);
  const rows = buildChannelPresentation(sample, unitMode);
  const boundedHistory = history?.length ? history : [sample];

  return (
    <section className="signal-source-card" aria-labelledby={sourceId}>
      <header className="signal-source-header">
        <h4 id={sourceId}>{sample.device_id}</h4>
        <p className="signal-applied-label" aria-label={mappingAccessibleText(sample)}>
          {mappingText(sample)}
        </p>
        <div className="signal-epochs">
          <span>Mapping epoch {sample.mapping_epoch}</span>
          <span>Reconnect epoch {sample.reconnect_epoch}</span>
        </div>
      </header>

      {rejection?.last_update_rejected && (
        <RejectionNotice rejection={rejection} hasAcceptedSample />
      )}

      <div className="signal-unit-control" role="group" aria-label={`Display units for ${sample.device_id}`}>
        <button
          type="button"
          className="mini-btn"
          aria-pressed={unitMode === 'raw'}
          onClick={() => setUnitMode('raw')}
        >
          Show Raw Counts
        </button>
        <button
          type="button"
          className="mini-btn"
          aria-pressed={unitMode === 'si'}
          disabled={!siAvailable}
          aria-describedby={!siAvailable ? siDisabledId : undefined}
          onClick={() => setUnitMode('si')}
        >
          Show SI Values
        </button>
        {!siAvailable && (
          <span id={siDisabledId} className="signal-control-reason">
            SI values are unavailable for every channel group. Raw counts remain available.
          </span>
        )}
      </div>

      <div className="signal-channel-table" aria-label={`Latest canonical values for ${sample.device_id}`}>
        {rows.map((channelRow) => (
          <ChannelRow
            row={channelRow}
            sourceId={sample.device_id}
            history={boundedHistory}
            unitMode={unitMode}
            key={channelRow.key}
          />
        ))}
      </div>

      <button
        type="button"
        className="mini-btn signal-provenance-toggle"
        aria-expanded={provenanceOpen}
        aria-controls={provenanceId}
        onClick={() => setProvenanceOpen((open) => !open)}
      >
        {provenanceOpen ? 'Hide Provenance' : 'Show Provenance'}
      </button>
      {provenanceOpen && (
        <div id={provenanceId} className="signal-provenance kv-grid">
          <span>Schema version</span><strong>{sample.schema}</strong>
          <span>Full MAC</span><strong>{sample.device_id}</strong>
          <span>Sequence</span><strong>{sample.sequence}</strong>
          <span>Sequence origin</span><strong>{sample.sequence_origin}</strong>
          <span>Acquisition time</span><strong>{sample.acquisition_time_us ?? 'Unavailable'}</strong>
          <span>Acquisition clock</span><strong>{sample.acquisition_clock ?? 'Unavailable'}</strong>
          <span>Bridge monotonic time</span><strong>{sample.bridge_monotonic_time_us}</strong>
          <span>Reconnect epoch</span><strong>{sample.reconnect_epoch}</strong>
          <span>Mapping provenance epoch</span><strong>{sample.mapping_epoch}</strong>
          <span>Applied revision</span><strong>{sample.applied_mapping.revision}</strong>
          <span>Exact segment</span><strong>{sample.applied_mapping.segment ?? 'Unassigned'}</strong>
          <span>Exact frame</span><strong>{sample.applied_mapping.frame ?? 'Unassigned'}</strong>
          <span>Model hash</span><strong>{sample.applied_mapping.model_hash}</strong>
          <span>Channel capabilities</span><strong>{capabilitiesText(sample)}</strong>
          <span>Validity reason codes</span><strong>{validityReasonCodes(sample)}</strong>
        </div>
      )}
    </section>
  );
}

export { RejectionNotice };

export interface SignalContractPanelViewProps {
  readonly snapshot: SignalSnapshot;
}

export function SignalContractPanelView({ snapshot }: SignalContractPanelViewProps) {
  const samples = Object.values(snapshot.canonicalSamplesByMac)
    .sort((left, right) => left.device_id.localeCompare(right.device_id));
  const rejectionOnly = Object.entries(snapshot.canonicalRejectionsBySource)
    .filter(([source, rejection]) => (
      rejection.last_update_rejected && !snapshot.canonicalSamplesByMac[source]
    ))
    .sort(([left], [right]) => left.localeCompare(right));
  const summary = snapshot.canonicalRejectedCount === 0
    ? <>{snapshot.canonicalAcceptedCount} accepted</>
    : (
      <>
        {snapshot.canonicalAcceptedCount} accepted ·{' '}
        <span className="signal-summary-rejected">{snapshot.canonicalRejectedCount} rejected</span>
      </>
    );

  return (
    <section className="dash-panel signal-contract-panel">
      <div className="dash-head">
        <h3>Signal Contract</h3>
        <span className="signal-contract-summary" role="status" aria-live="polite">
          {summary}
        </span>
      </div>

      {samples.length === 0 && rejectionOnly.length === 0 && (
        <div className="signal-empty-state">
          <strong>No canonical samples</strong>
          <span>Start acquisition or check the ROS bridge connection.</span>
        </div>
      )}

      <div className="signal-source-list">
        {samples.map((canonicalSample) => (
          <SignalSourceCard
            key={canonicalSample.device_id}
            sample={canonicalSample}
            history={snapshot.canonicalHistoryByMac[canonicalSample.device_id]}
            rejection={snapshot.canonicalRejectionsBySource[canonicalSample.device_id]}
          />
        ))}
        {rejectionOnly.map(([source, rejection]) => (
          <div className="signal-rejection-only" key={source}>
            {rejection.device_id !== null && <strong>{rejection.device_id}</strong>}
            <RejectionNotice rejection={rejection} hasAcceptedSample={false} />
          </div>
        ))}
      </div>
    </section>
  );
}

export function SignalContractPanel({ snapshot }: SignalContractPanelViewProps) {
  return <SignalContractPanelView snapshot={snapshot} />;
}
