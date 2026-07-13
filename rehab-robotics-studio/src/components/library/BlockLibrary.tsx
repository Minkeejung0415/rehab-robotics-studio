import { useMemo, useState } from 'react';
import type { BlockDefinition } from '../../types/blocks';
import type { SignalType } from '../../types/signals';
import { BLOCK_DEFS, CATEGORY_ORDER } from '../../graph/blockDefinitions';
import { useBlockRegistryStore } from '../../state/blockRegistryStore';
import { useGraphStore } from '../../state/graphStore';
import { useSystemStore } from '../../state/systemStore';
import { categoryColor } from '../../theme/tokens';
import { LibraryItem } from './LibraryItem';

const VALID_SIGNAL_TYPES = new Set<string>([
  'number', 'bool', 'event', 'force3d', 'emg_signal', 'imu',
  'motor_state', 'joint_state', 'system_status',
]);

function parseBlockManifest(json: unknown, folderName: string): BlockDefinition | null {
  if (!json || typeof json !== 'object' || Array.isArray(json)) {
    alert('block.json must be a JSON object.');
    return null;
  }
  const raw = json as Record<string, unknown>;

  if (typeof raw.name !== 'string' || !raw.name.trim()) {
    alert('block.json must have a "name" string field.');
    return null;
  }
  if (!Array.isArray(raw.inputs)) {
    alert('block.json must have an "inputs" array (can be empty []).');
    return null;
  }
  if (!Array.isArray(raw.outputs)) {
    alert('block.json must have an "outputs" array (can be empty []).');
    return null;
  }

  const slug = folderName.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
  const type = `custom_${slug || 'block'}`;

  const toPort = (p: unknown, dir: 'in' | 'out', idx: number) => {
    const obj = (p && typeof p === 'object' && !Array.isArray(p)) ? p as Record<string, unknown> : {};
    const name = typeof obj.name === 'string' ? obj.name : `${dir}${idx}`;
    const signalType: SignalType = (typeof obj.signalType === 'string' && VALID_SIGNAL_TYPES.has(obj.signalType))
      ? obj.signalType as SignalType
      : 'number';
    return { id: name, name, dir, signalType, ...(dir === 'in' ? { required: false } : {}) };
  };

  const inputs = (raw.inputs as unknown[]).map((p, i) => toPort(p, 'in', i));
  const outputs = (raw.outputs as unknown[]).map((p, i) => toPort(p, 'out', i));

  const params = Array.isArray(raw.params)
    ? (raw.params as unknown[]).map((p) => {
        const obj = (p && typeof p === 'object' && !Array.isArray(p)) ? p as Record<string, unknown> : {};
        const key = typeof obj.key === 'string' ? obj.key : 'param';
        const label = typeof obj.label === 'string' ? obj.label : key;
        const ptype = (['number', 'enum', 'bool', 'text'] as string[]).includes(obj.type as string)
          ? obj.type as 'number' | 'enum' | 'bool' | 'text'
          : 'number';
        const def = obj.default ?? (ptype === 'number' ? 0 : ptype === 'bool' ? false : '');
        const extra: Record<string, unknown> = {};
        if (typeof obj.unit === 'string') extra.unit = obj.unit;
        if (typeof obj.min === 'number') extra.min = obj.min;
        if (typeof obj.max === 'number') extra.max = obj.max;
        if (typeof obj.step === 'number') extra.step = obj.step;
        if (Array.isArray(obj.options)) extra.options = obj.options;
        return { key, label, type: ptype, default: def as string | number | boolean, ...extra };
      })
    : [];

  return {
    type,
    name: raw.name.trim(),
    category: (typeof raw.category === 'string' ? raw.category : 'User Plugins') as BlockDefinition['category'],
    runtime: 'plugin-later',
    safeForMotorControl: raw.safeForMotorControl === true,
    inputs,
    outputs,
    params,
    description: typeof raw.description === 'string'
      ? raw.description
      : `Custom block loaded from ${folderName}/`,
  };
}

export function BlockLibrary() {
  const [query, setQuery] = useState('');
  const addNode = useGraphStore((s) => s.addNode);
  const nodeCount = useGraphStore((s) => s.nodes.length);
  const customDefs = useBlockRegistryStore((s) => s.customDefs);
  const registerBlock = useBlockRegistryStore((s) => s.registerBlock);

  const allDefs = useMemo(() => ({ ...BLOCK_DEFS, ...customDefs }), [customDefs]);

  const handleAdd = (type: string) => {
    const x = 360 + (nodeCount % 4) * 30;
    const y = 60 + (nodeCount % 6) * 30;
    addNode(type, x, y);
    useSystemStore.getState().addLog('INFO', `Added block: ${allDefs[type]?.name ?? type}`);
  };

  const handleLoadFolder = async () => {
    if (!('showDirectoryPicker' in window)) {
      alert('Your browser does not support the File System Access API. Use Chrome or Edge.');
      return;
    }

    let dir: FileSystemDirectoryHandle;
    try {
      dir = await (window as unknown as {
        showDirectoryPicker: (opts?: object) => Promise<FileSystemDirectoryHandle>;
      }).showDirectoryPicker({ mode: 'read' });
    } catch {
      return; // user cancelled
    }

    let fileHandle: FileSystemFileHandle;
    try {
      fileHandle = await dir.getFileHandle('block.json');
    } catch {
      alert(`No block.json found in "${dir.name}".`);
      return;
    }

    let json: unknown;
    try {
      const text = await (await fileHandle.getFile()).text();
      json = JSON.parse(text);
    } catch {
      alert('block.json contains invalid JSON.');
      return;
    }

    const def = parseBlockManifest(json, dir.name);
    if (!def) return;

    registerBlock(def);
    useSystemStore.getState().addLog('INFO', `Registered custom block: ${def.name}`);
  };

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    return CATEGORY_ORDER.map((cat) => ({
      cat,
      defs: Object.values(allDefs).filter(
        (d) => d.category === cat && (q === '' || d.name.toLowerCase().includes(q)),
      ),
    })).filter((g) => g.defs.length > 0);
  }, [query, allDefs]);

  return (
    <aside className="library">
      <div className="panel-heading">BLOCK PALETTE</div>
      <div className="library-search">
        <input
          placeholder="Search blocks…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>
      <div className="library-scroll">
        {grouped.map((g) => (
          <div key={g.cat}>
            <div className="palette-cat">
              <span className="palette-cat-dot" style={{ background: categoryColor[g.cat] }} />
              {g.cat}
            </div>
            {g.defs.map((def) => (
              <LibraryItem key={def.type} def={def} onAdd={handleAdd} />
            ))}
          </div>
        ))}
      </div>
      <div className="library-footer">
        <button className="btn-load-block" onClick={handleLoadFolder}>
          + Load Block from Folder
        </button>
      </div>
      <div className="library-hint">Double-click or + to add · drag to canvas</div>
    </aside>
  );
}
