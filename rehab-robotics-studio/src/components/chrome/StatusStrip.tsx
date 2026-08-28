/** Persistent bottom-line summary of runtime and connection state from systemStore. */
import { useSystemStore } from '../../state/systemStore';
import { StatusLight } from '../common/StatusLight';

export function StatusStrip() {
  const status = useSystemStore((state) => state.status);
  const items = [status.ros, status.jetson, status.redPitaya, status.motor, status.recording, status.fault];
  return (
    <div className="status-strip">
      {items.map((indicator) => (
        <StatusLight key={indicator.label} label={indicator.label} value={indicator.value} level={indicator.level} />
      ))}
    </div>
  );
}
