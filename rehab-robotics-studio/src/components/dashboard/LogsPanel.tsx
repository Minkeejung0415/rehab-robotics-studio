import { useSystemStore } from '../../state/systemStore';

export function LogsPanel() {
  const logs = useSystemStore((state) => state.logs);
  const clearLogs = useSystemStore((state) => state.clearLogs);
  return (
    <section className="dash-panel logs-panel">
      <div className="dash-head">
        <h3>System Log</h3>
        <button className="mini-btn" onClick={clearLogs}>Clear</button>
      </div>
      <div className="logs-list">
        {logs.slice().reverse().map((log) => (
          <div key={log.id} className={`log-row level-${log.level.toLowerCase()}`}>
            <span>{log.t}</span><b>{log.level}</b><em>{log.message}</em>
          </div>
        ))}
      </div>
    </section>
  );
}
