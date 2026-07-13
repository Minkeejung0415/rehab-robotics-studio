# External Integrations

**Analysis Date:** 2026-07-13

## APIs & External Services

**Hardware (Planned — NOT yet implemented):**

All hardware integrations are defined as mock block stubs in the block registry
(`rehab-robotics-studio/src/graph/blockDefinitions.ts`) with `runtime: 'mock'`.
The `DataSource` interface (`rehab-robotics-studio/src/data/DataSource.ts`) is the
designed seam for dropping in real adapters.

- **Red Pitaya** — Raw analog acquisition board over TCP
  - Planned: `RosbridgeDataSource` / `RedPitayaDataSource` implementing `DataSource`
  - Mock block: `fake_red_pitaya_stream` with IP param default `'192.168.1.50'`
  - Current: `MockDataSource` singleton (`rehab-robotics-studio/src/data/MockDataSource.ts`)

- **ROS / rosbridge** — Robot middleware
  - Planned: `RosbridgeDataSource` implementing `DataSource`
  - Shown in system status as `'Mock Connected'` (`rehab-robotics-studio/src/state/systemStore.ts`)
  - Not connected to any actual WebSocket or rosbridge server

- **Jetson Orin** — Edge compute target for graph deployment
  - Planned: graph push via `actions.deployMock()` (`rehab-robotics-studio/src/state/actions.ts`)
  - Current: logs only ("graph would be pushed to Jetson")

- **EtherCAT Motor Controller** — Actuator command bus
  - Planned: real motor command output from `motor_command_mock` block
  - Current: mock only

- **OpenSim** — Biomechanics inverse-kinematics solver
  - Planned: real solver execution via `opensim_ik_mock` block
  - Current: mock sine-wave output

**User Plugin Runtimes (Planned — NOT yet implemented):**

- **Python subprocess** — via `python_function_mock` block (`runtime: 'plugin-later'`)
  - Planned: sandboxed Python execution, script path param
- **MATLAB Engine** — via `matlab_function_mock` block (`runtime: 'plugin-later'`)
  - Planned: MATLAB engine bridge, script path param

## Data Storage

**Databases:**
- None. No database is used.

**File Storage:**
- Browser `Blob` + `URL.createObjectURL` for project save/download
  - File: `rehab-robotics-studio.rasproj.json`
  - Implementation: `rehab-robotics-studio/src/state/actions.ts` `saveProject()`
- Browser File Picker (`<input type="file">`) for project load
  - Implementation: `rehab-robotics-studio/src/components/chrome/Toolbar.tsx`
- Planned: CSV file recording via `csv_recorder_mock` block (file I/O not yet implemented)

**Caching:**
- None. All state is in-memory Zustand stores.

## Authentication & Identity

**Auth Provider:**
- None. No authentication is implemented or planned.

## Monitoring & Observability

**Error Tracking:**
- None. No external error tracking service is integrated.

**Logs:**
- In-app log panel (`rehab-robotics-studio/src/components/dashboard/LogsPanel.tsx`)
- Ring-buffered in `useSystemStore` (last 300 entries, `rehab-robotics-studio/src/state/systemStore.ts`)
- Log levels: `INFO`, `WARN`, `ERROR`, `SAFETY`
- No external log forwarding

## CI/CD & Deployment

**Hosting:**
- Not configured. Project is a local prototype.
- Build output: `dist/` (standard Vite static files, deployable to any static host)

**CI Pipeline:**
- None detected. No `.github/`, `.gitlab-ci.yml`, or similar CI config.

## Environment Configuration

**Required env vars:**
- None. The app has no env var dependencies.

**Secrets location:**
- No secrets. All configuration is in source or user-supplied block parameters.

## Webhooks & Callbacks

**Incoming:**
- None.

**Outgoing:**
- None. All "outgoing" actions (deploy to Jetson, ROS publish, EtherCAT command) are currently stubs.

## Signal Data Flow (Internal Runtime)

The app has an internal pub/sub data pipeline that is the architectural equivalent of a hardware integration layer:

```
MockDataSource (setInterval, ~8–40 ms)
  └─> SignalBus.ingest() — runs graph executor at data rate
        └─> requestAnimationFrame loop (~30 fps)
              └─> useSyncExternalStore listeners → React render
```

**Key files:**
- `rehab-robotics-studio/src/data/DataSource.ts` — interface contract for any real adapter
- `rehab-robotics-studio/src/data/MockDataSource.ts` — current implementation
- `rehab-robotics-studio/src/data/signalBus.ts` — rate-decoupling bus
- `rehab-robotics-studio/src/hooks/useSignals.ts` — React hook consuming the bus

---

*Integration audit: 2026-07-13*
