import { useState } from 'react';
import { GraphCanvas } from './components/canvas/GraphCanvas';
import { StatusStrip } from './components/chrome/StatusStrip';
import { Toolbar } from './components/chrome/Toolbar';
import { Dashboard } from './components/dashboard/Dashboard';
import { BlockLibrary } from './components/library/BlockLibrary';
import { MappingWorkspace } from './components/mapping/MappingWorkspace';
import { PropertiesPanel } from './components/properties/PropertiesPanel';

type WorkspaceTab = 'diagram' | 'panel' | 'mapping';

/**
 * Top-level shell and workspace switcher.
 *
 * Add a new full-screen workspace by extending WorkspaceTab, adding its tab
 * button here, and rendering the feature component below. Shared controls
 * belong in Toolbar/StatusStrip so all workspaces behave consistently.
 */
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
        <button
          className={`tab${activeTab === 'mapping' ? ' is-active' : ''}`}
          onClick={() => setActiveTab('mapping')}
        >
          Sensor Mapping
        </button>
      </div>
      {activeTab === 'diagram' ? (
        <main className="workspace">
          <BlockLibrary />
          <GraphCanvas />
          <PropertiesPanel />
        </main>
      ) : activeTab === 'panel' ? (
        <main className="workspace workspace--front-panel">
          <Dashboard />
        </main>
      ) : (
        <main className="workspace workspace--mapping">
          <MappingWorkspace />
        </main>
      )}
      <StatusStrip />
    </div>
  );
}
