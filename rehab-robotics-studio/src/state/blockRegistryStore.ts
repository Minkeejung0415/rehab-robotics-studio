/** Runtime registry for user-defined block definitions and their default parameters. */
import { create } from 'zustand';
import type { BlockDefinition } from '../types/blocks';

const STORAGE_KEY = 'rehab-robotics:customBlocks';

function loadFromStorage(): Record<string, BlockDefinition> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    return JSON.parse(raw) as Record<string, BlockDefinition>;
  } catch {
    return {};
  }
}

function saveToStorage(defs: Record<string, BlockDefinition>): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(defs));
  } catch {
    // quota exceeded or private browsing — silently ignore
  }
}

interface BlockRegistryState {
  customDefs: Record<string, BlockDefinition>;
  registerBlock: (def: BlockDefinition) => void;
  removeBlock: (type: string) => void;
}

export const useBlockRegistryStore = create<BlockRegistryState>((set, get) => ({
  customDefs: loadFromStorage(),

  registerBlock: (def) => {
    const next = { ...get().customDefs, [def.type]: def };
    saveToStorage(next);
    set({ customDefs: next });
  },

  removeBlock: (type) => {
    const next = { ...get().customDefs };
    delete next[type];
    saveToStorage(next);
    set({ customDefs: next });
  },
}));

/** Synchronous getter for use outside React components (e.g. in graphStore). */
export function getCustomDef(type: string): BlockDefinition | undefined {
  return useBlockRegistryStore.getState().customDefs[type];
}

/** Build a default params object from any BlockDefinition (not just BLOCK_DEFS). */
export function defaultParamsFromDef(def: BlockDefinition): Record<string, string | number | boolean> {
  const params: Record<string, string | number | boolean> = {};
  for (const p of def.params) params[p.key] = p.default;
  return params;
}
