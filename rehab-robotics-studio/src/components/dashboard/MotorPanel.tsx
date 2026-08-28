/** Motor telemetry display. It does not grant motor control authority. */
import { signalColor } from '../../theme/tokens';
import { useSignals } from '../../hooks/useSignals';
import {
  formatLiveKneeAngle,
  selectLiveKneeAngleSeries,
} from '../../data/liveKneeAngle';
import { MiniChart } from '../common/MiniChart';

export function MotorPanel() {
  const { motor, kneeAngle, kneeSeries } = useSignals();
  const kneeDisplay = formatLiveKneeAngle(kneeAngle);
  const visibleKneeSeries = selectLiveKneeAngleSeries(kneeAngle, kneeSeries);

  return (
    <section className="dash-panel">
      <div className="dash-head">
        <h3>Motor / Joint</h3>
        <span className={`motor-pill ${motor.fault ? 'fault' : motor.enabled ? 'enabled' : ''}`}>
          {motor.fault ? 'FAULT' : motor.enabled ? 'ENABLED' : 'DISABLED'}
        </span>
      </div>
      <div className="readout-grid">
        <span>Knee</span>
        <div
          className={`knee-angle-readout ${kneeDisplay.isLive ? 'is-live' : 'is-unavailable'}`}
          data-state={kneeDisplay.isLive ? 'live' : 'unavailable'}
        >
          <strong className="knee-angle-value">{kneeDisplay.valueText}</strong>
          {kneeDisplay.statusText && (
            <span className="knee-angle-status">{kneeDisplay.statusText}</span>
          )}
        </div>
        <span>Position</span><strong>{motor.position.toFixed(2)} rad</strong>
        <span>Velocity</span><strong>{motor.velocity.toFixed(2)} rad/s</strong>
        <span>Torque</span><strong>{motor.torque.toFixed(2)} Nm</strong>
        <span>Current</span><strong>{motor.current.toFixed(2)} A</strong>
        <span>Temp</span><strong>{motor.temperature.toFixed(1)} C</strong>
      </div>
      <MiniChart data={visibleKneeSeries} color={signalColor.joint_state} height={48} />
    </section>
  );
}
