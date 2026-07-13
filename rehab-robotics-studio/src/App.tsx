import { useState } from 'react';
import { GraphCanvas } from './components/canvas/GraphCanvas';
import { StatusStrip } from './components/chrome/StatusStrip';
import { Toolbar } from './components/chrome/Toolbar';
import { Dashboard } from './components/dashboard/Dashboard';
import { BlockLibrary } from './components/library/BlockLibrary';
import { PropertiesPanel } from './components/properties/PropertiesPanel';

type WorkspaceTab = 'diagram' | 'panel';

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
          className={`tab${activeTab === 'panel' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('panel')}
        >
          Front Panel
        </button>
      </div>
      {activeTab === 'diagram' ? (
        <main className="workspace">
          <BlockLibrary />
          <GraphCanvas />
          <PropertiesPanel />
        </main>
      ) : (
        <main className="workspace workspace--front-panel">
          <Dashboard />
        </main>
      )}
      <StatusStrip />
    </div>
  );
}
