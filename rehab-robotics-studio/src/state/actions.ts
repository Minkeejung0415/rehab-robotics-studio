import { useGraphStore } from './graphStore';
import { useSystemStore } from './systemStore';

export const actions = {
  validateGraph(): void {
    const issues = useGraphStore.getState().validate();
    const system = useSystemStore.getState();
    if (issues.length === 0) { system.addLog('INFO', 'Graph validation passed — no issues'); return; }
    system.addLog('INFO', `Graph validation: ${issues.length} issue(s)`);
    for (const issue of issues) system.addLog(issue.level, issue.message);
  },
  saveProject(): void {
    const json = useGraphStore.getState().serialize();
    try {
      const blob = new Blob([json], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'rehab_robotics.rasproj.json';
      link.click();
      URL.revokeObjectURL(url);
    } catch { /* Download is unavailable during server-side tests. */ }
    useSystemStore.getState().addLog('INFO', `Project saved — ${json.length} bytes serialized`);
  },
  loadProject(json: string): void {
    try { useGraphStore.getState().load(json); useSystemStore.getState().addLog('INFO', 'Project loaded'); }
    catch (error) { useSystemStore.getState().addLog('ERROR', `Load failed: ${(error as Error).message}`); }
  },
  deployMock(): void { useSystemStore.getState().addLog('INFO', 'Deploy (mock) — graph would be pushed to Jetson'); },
  async deployProcessingBlocks(): Promise<{ success: boolean; message: string }> {
    const issues = useGraphStore.getState().validate();
    if (issues.some((issue) => issue.level === 'ERROR' || issue.level === 'SAFETY')) {
      const message = 'Deploy blocked — resolve graph errors and safety findings first.';
      useSystemStore.getState().addLog('ERROR', message);
      return { success: false, message };
    }
    const message = 'Deploy validation passed. Processing-block publishing is parked for a later milestone.';
    useSystemStore.getState().addLog('INFO', message);
    return { success: true, message };
  },
};
