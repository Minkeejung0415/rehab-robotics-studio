import { useEffect } from 'react';
import { useGraphStore } from '../state/graphStore';

export function useKeyboardDelete(): void {
  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key !== 'Delete' && event.key !== 'Backspace') return;

      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

      const { selectedId, selectedEdgeId, removeNode, removeEdge } = useGraphStore.getState();
      if (selectedId) {
        event.preventDefault();
        removeNode(selectedId);
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
