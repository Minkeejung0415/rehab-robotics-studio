# Phase 5 Playwright Issues Log

**Policy:** Record failures; do not auto-fix until user reviews.

**Run:** 2026-07-13T21:40:53.254Z
**Base URL:** http://127.0.0.1:4173/
**Script:** scripts/phase5-qa.mjs
**Headless:** false
**Summary:** 10 PASS / 0 FAIL / 10 total

| # | Req | Check | Result | Details | Expected | Actual |
|---|-----|-------|--------|---------|----------|--------|
| 1 | TAB-01 | Tab strip visible with Block Diagram and Front Panel tabs | **PASS** | stripVisible=true, tabCount=2, tabs=[Block Diagram, Front Panel] | .tab-strip with 2 .tab children: "Block Diagram" and "Front Panel" | tabCount=2, tabs=[Block Diagram, Front Panel] |
| 2 | TAB-01 | Default active tab is "Block Diagram" | **PASS** | activeCount=1, activeText="Block Diagram" | Exactly 1 .tab.is-active; text = "Block Diagram" | activeCount=1, text="Block Diagram" |
| 3 | TAB-02 | Block Diagram tab shows Library + Canvas + Properties; no Dashboard | **PASS** | library=true, canvas=true, properties=true, dashboard=false | .library, .graph-canvas, .properties visible; .dashboard not visible | library=true, canvas=true, props=true, dash=false |
| 4 | TAB-03 | Front Panel tab → .workspace--front-panel + .dashboard + .dash-panel visible | **PASS** | fpVisible=true, dashVisible=true, dashPanels=4 | .workspace--front-panel visible; .dashboard visible; at least 1 .dash-panel | fpVisible=true, dashVisible=true, dashPanels=4 |
| 5 | TAB-03 | Front Panel tab hides graph canvas and library | **PASS** | canvasVisible=false, libraryVisible=false | .graph-canvas and .library not visible in Front Panel tab | canvas=false, library=false |
| 6 | TAB-04 | Front Panel tab has is-active class when selected | **PASS** | activeText="Front Panel" | .tab.is-active text = "Front Panel" | activeText="Front Panel" |
| 7 | TAB-02 | Click Block Diagram → canvas visible; dashboard gone | **PASS** | canvasVisible=true, dashboardVisible=false | .graph-canvas visible; .dashboard not visible | canvas=true, dashboard=false |
| 8 | REG | Toolbar visible in both Block Diagram and Front Panel tabs | **PASS** | inDiagram=true, inFrontPanel=true | .toolbar visible in both tabs | inDiagram=true, inFrontPanel=true |
| 9 | REG | Status strip visible in both Block Diagram and Front Panel tabs | **PASS** | inDiagram=true, inFrontPanel=true | .status-strip visible in both tabs | inDiagram=true, inFrontPanel=true |
| 10 | REG | Phase 4 regression: blocks on canvas + Deploy toast works | **PASS** | blockCount=11, toastOk=true, toasts=[Deploy (mock) started — graph would be pushed to Jetson] | Blocks present on canvas; Deploy Mock shows toast | blocks=11, toastOk=true |

## Failures

_None — all checklist items passed._
