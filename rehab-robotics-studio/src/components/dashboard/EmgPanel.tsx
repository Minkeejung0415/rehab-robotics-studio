/** EMG front-panel presentation backed by the shared signal bus. */
import { signalColor } from '../../theme/tokens';
import { useSignals } from '../../hooks/useSignals';
import { MiniChart } from '../common/MiniChart';

export function EmgPanel() {
  const signals = useSignals();
  return (
    <section className="dash-panel">
      <div className="dash-head">
        <h3>EMG</h3>
        <span className="type-badge" style={{ color: signalColor.emg_signal, borderColor: `${signalColor.emg_signal}55` }}>CH 1</span>
      </div>
      <div className="readout-grid">
        <span>Raw</span><strong>{signals.emgRaw.toFixed(3)} mV</strong>
        <span>Envelope</span><strong>{signals.emgEnvelope.toFixed(3)} mV</strong>
      </div>
      <MiniChart data={signals.emgSeries} color={signalColor.emg_signal} height={86} />
    </section>
  );
}
