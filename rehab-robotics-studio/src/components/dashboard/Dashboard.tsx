/** Front-panel composition for live sensor, OpenSim, and health views. */
import { useEffect, useRef } from 'react';
import { EmgPanel } from './EmgPanel';
import { ForcePanel } from './ForcePanel';
import { LogsPanel } from './LogsPanel';
import { MotorPanel } from './MotorPanel';
import { HealthPanel } from './HealthPanel';
import { SignalContractPanel, rejectionReasonText } from './SignalContractPanel';
import { useSignals } from '../../hooks/useSignals';
import { useSystemStore } from '../../state/systemStore';

export function Dashboard() {
  const signalSnapshot = useSignals();
  const addLog = useSystemStore((state) => state.addLog);
  const loggedRejections = useRef(new Map<string, string>());

  useEffect(() => {
    for (const rejection of Object.values(signalSnapshot.canonicalRejectionsBySource)) {
      if (!rejection.last_update_rejected || !rejection.should_announce) continue;
      const source = rejection.device_id ?? 'unknown source';
      const signature = `${rejection.reason}:${rejection.count}`;
      if (loggedRejections.current.get(source) === signature) continue;
      loggedRejections.current.set(source, signature);
      addLog(
        'WARN',
        `Signal sample rejected (${source}): ${rejectionReasonText(rejection.reason)}`,
      );
    }
  }, [addLog, signalSnapshot.canonicalRejectionsBySource]);

  return (
    <aside className="dashboard">
      <div className="panel-heading">LIVE DASHBOARD</div>
      <SignalContractPanel snapshot={signalSnapshot} />
      <HealthPanel />
      <ForcePanel />
      <EmgPanel />
      <MotorPanel />
      <LogsPanel />
    </aside>
  );
}
