# Phase 4 Playwright Issues Log

**Policy:** Record failures; do not auto-fix until user reviews.

**Run:** 2026-07-13T21:33:50.605Z
**Base URL:** http://127.0.0.1:4173/
**Script:** scripts/phase4-qa.mjs
**Headless:** false
**Summary:** 10 PASS / 0 FAIL / 10 total

| # | Req | Check | Result | Details | Expected | Actual |
|---|-----|-------|--------|---------|----------|--------|
| 1 | RT-01 | Run → every block status-badge is running | **PASS** | badges=[running, running, running, running, running, running, running, running, running, running, running] count=11 | Every .block-node .status-badge text includes "running" | running, running, running, running, running, running, running, running, running, running, running |
| 2 | RT-01 | Pause → badges still running; RUNTIME PAUSED if visible | **PASS** | badges=[running, running, running, running, running, running, running, running, running, running, running], runtime="PAUSED" | Badges include "running"; RUNTIME shows PAUSED when visible | badges=running, running, running, running, running, running, running, running, running, running, running; runtime=PAUSED |
| 3 | RT-01 | Stop → all badges idle | **PASS** | badges=[idle, idle, idle, idle, idle, idle, idle, idle, idle, idle, idle] | Every .status-badge text includes "idle" | idle, idle, idle, idle, idle, idle, idle, idle, idle, idle, idle |
| 4 | RT-02 | Rec button visible; click → Recording On/active | **PASS** | visible=true, before="○ Rec", after="● Rec", strip={"found":true,"value":"On","color":"rgb(236, 90, 90)"}, btn-rec-on=true | ○ Rec (or similar) visible; after click Recording strip On + active/red chrome | btn="● Rec", strip.value="On", btn-rec-on=true |
| 5 | RT-02 | Rec again → Recording Off | **PASS** | after="○ Rec", strip={"found":true,"value":"Off","color":"rgb(107, 115, 120)"}, btn-rec-on=false | Recording strip Off; Rec not pressed/active | btn="○ Rec", strip.value="Off", btn-rec-on=false |
| 6 | RT-02 | Rec disabled when E-STOP engaged (optional) | **PASS** | recDisabled=true | Rec button disabled while E-STOP engaged | disabled=true |
| 7 | DEP-01 | Deploy Mock → toast contains "Deploy (mock) started" AND log entry | **PASS** | toasts=[Deploy (mock) started — graph would be pushed to Jetson], logOk=true | Toast text contains "Deploy (mock) started"; System Log has deploy entry | toasts=[Deploy (mock) started — graph would be pushed to Jetson]; logPresent=true |
| 8 | DEP-01 | Toast auto-dismisses or click-dismiss works | **PASS** | mode=click-dismiss, afterClickCount=0 | Toast dismisses via click and/or ~2500ms auto-dismiss | dismissed via click-dismiss |
| 9 | DEP-01 | Second Deploy replaces toast (single toast) | **PASS** | firstCount=1, secondCount=1, texts=[Deploy (mock) started — graph would be pushed to Jetson], firstText="Deploy (mock) started — graph would be pushed to Jetson" | Exactly one .toast after second Deploy; copy still present | toastCount=1; texts=[Deploy (mock) started — graph would be pushed to Jetson] |
| 10 | REG | Context menu still opens on block right-click | **PASS** | labels=[Duplicate / Rename / Delete] | Custom .context-menu visible with Duplicate/Rename/Delete | labels=[Duplicate / Rename / Delete] |

## Failures

_None — all checklist items passed._
