# Technology Stack

**Analysis Date:** 2026-07-13

## Languages

**Primary:**
- TypeScript 5.6.3 - All application source (`rehab-robotics-studio/src/`)

**Secondary:**
- CSS - Layout and theming (`rehab-robotics-studio/src/styles/app.css`)
- HTML - Single entry point (`rehab-robotics-studio/index.html`, `Rehab Robotics Builder.dc.html`)

## Runtime

**Environment:**
- Browser (Web API — `requestAnimationFrame`, `setInterval`, `performance.now()`, Blob/URL download)
- No Node.js server component; fully client-side SPA

**Package Manager:**
- npm
- Lockfile: `rehab-robotics-studio/package-lock.json` (present)

## Frameworks

**Core:**
- React 18.3.1 - Component rendering, UI (`rehab-robotics-studio/src/`)
- `useSyncExternalStore` (React built-in) - Bridging the signal bus to React renders (`rehab-robotics-studio/src/hooks/useSignals.ts`)

**State Management:**
- Zustand 4.5.5 - Three independent stores: `graphStore`, `systemStore`, `runtimeStore` (`rehab-robotics-studio/src/state/`)

**Build/Dev:**
- Vite 5.4.11 - Dev server (port 5173) and production bundler (`rehab-robotics-studio/vite.config.ts`)
- `@vitejs/plugin-react` 4.3.4 - React fast refresh + JSX transform
- TypeScript compiler (`tsc`) - Type checking only (`tsc -b && vite build`)

**Testing:**
- None detected. No test framework configured.

## Key Dependencies

**Critical:**
- `react` 18.3.1 - UI framework
- `react-dom` 18.3.1 - DOM renderer
- `zustand` 4.5.5 - Application state (graph, runtime, system status)

**Infrastructure:**
- `@types/node` 26.0.1 - Node type definitions (used in `vite.config.ts` for `node:fs`, `node:path`, `node:url`)
- `typescript` 5.6.3 - Static typing, strict mode enabled
- `postcss`, `esbuild`, `rollup` - Bundler internals (transitive via Vite)

**No external UI library** - All components use custom CSS (`rehab-robotics-studio/src/styles/app.css`) and inline SVG for canvas rendering.

**No charting library** - All waveform rendering is done via custom `MiniChart` (`rehab-robotics-studio/src/components/common/MiniChart.tsx`) using SVG `<polyline>`.

## Configuration

**Environment:**
- No `.env` files detected. No runtime environment variables are consumed by the app.
- Hardware endpoint (Red Pitaya IP) is stored as a block parameter default (`'192.168.1.50'`) in `rehab-robotics-studio/src/graph/blockDefinitions.ts` — not an env var.

**TypeScript:**
- `rehab-robotics-studio/tsconfig.json` — strict mode on, target ES2020, `moduleResolution: bundler`, `jsx: react-jsx`
- `rehab-robotics-studio/tsconfig.node.json` — separate config for Vite config file itself

**Build:**
- `rehab-robotics-studio/vite.config.ts` — registers `@vitejs/plugin-react` and a custom `extensionlessRelativeResolver` plugin that resolves extension-less relative imports (`.tsx`, `.ts`, `.jsx`, `.js`)
- Build command: `tsc -b && vite build`

## Platform Requirements

**Development:**
- Node.js (version not pinned — no `.nvmrc` or `.node-version`)
- npm install then `npm run dev` serves at `http://localhost:5173`

**Production:**
- Static file host — `vite build` emits a `dist/` folder of plain HTML/JS/CSS
- No backend required
- No server-side rendering

---

*Stack analysis: 2026-07-13*
