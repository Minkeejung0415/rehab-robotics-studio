import { useRuntimeStore } from '../../state/runtimeStore';
import { signalColor } from '../../theme/tokens';
import { useSignals } from '../../hooks/useSignals';
import { Gauge } from '../common/Gauge';
import { MiniChart } from '../common/MiniChart';

export function ForcePanel() {
  const signals = useSignals();
  const tare = useRuntimeStore((state) => state.tare);
  return (
    <section className="dash-panel">
      <div className="dash-head"><h3>Force</h3><button className="mini-btn" onClick={tare}>Tare</button></div>
      <Gauge value={signals.forceProcessed} min={-50} max={50} units="N" color={signalColor.force3d} />
      <div className="readout-grid">
        <span>Raw Fz</span><strong>{signals.forceRaw.toFixed(2)} N</strong>
        <span>Filtered</span><strong>{signals.forceProcessed.toFixed(2)} N</strong>
      </div>
      <MiniChart data={signals.forceSeries} color={signalColor.force3d} height={54} />
    </section>
  );
}
