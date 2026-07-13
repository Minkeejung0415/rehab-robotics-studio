import { useEffect } from 'react';
import { useGraphStore } from '../state/graphStore';

export function useKeyboardDelete(): void {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' && event.key !== 'Backspace') return;

      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      const { selectedIds, selectedEdgeId, removeNodes, removeEdge } = useGraphStore.getState();
      if (selectedIds.length > 0) {
        event.preventDefault();
        removeNodes(selectedIds);
        return;
      }

      if (selectedEdgeId) {
        event.preventDefault();
        removeEdge(selectedEdgeId);
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
}
