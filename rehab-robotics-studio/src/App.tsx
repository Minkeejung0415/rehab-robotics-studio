import { useState } from 'react';
import { GraphCanvas } from './components/canvas/GraphCanvas';
import { StatusStrip } from './components/chrome/StatusStrip';
import { Toolbar } from './components/chrome/Toolbar';
import { Dashboard } from './components/dashboard/Dashboard';
import { BlockLibrary } from './components/library/BlockLibrary';
import { PropertiesPanel } from './components/properties/PropertiesPanel';

type WorkspaceTab = 'diagram' | 'palette' | 'panel';

export default function App() {
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('diagram');

  return (
    <div className="app-shell">
      <Toolbar />
      <div className="tab-strip">
        <button
          className={`tab${activeTab === 'diagram' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('diagram')}
        >
          Block Diagram
        </button>
        <button
          className={`tab${activeTab === 'palette' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('palette')}
        >
          Block Palette
        </button>
        <button
          className={`tab${activeTab === 'panel' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('panel')}
        >
          Front Panel
        </button>
      </div>
      {activeTab === 'diagram' && (
        <main className="workspace workspace--diagram">
          <GraphCanvas />
          <PropertiesPanel />
        </main>
      )}
      {activeTab === 'palette' && (
        <main className="workspace workspace--palette">
          <BlockLibrary />
        </main>
      )}
      {activeTab === 'panel' && (
        <main className="workspace workspace--front-panel">
          <Dashboard />
        </main>
      )}
      <StatusStrip />
    </div>
  );
}
