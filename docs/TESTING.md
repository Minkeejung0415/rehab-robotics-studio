<!-- generated-by: gsd-doc-writer -->
# Testing

## Studio

```powershell
cd rehab-robotics-studio
npm test
npm run typecheck
npm run build
```

Studio tests는 `*.test.ts` 또는 `*.test.tsx` 명명 규칙을 사용하며, state/data/graph/component 경계의 동작을 다룬다.

## Backend

`backend/test/`에는 Python 기반 ROS bridge, signal/measurement contract, mapping, OpenSim, UDP relay 테스트가 있다. ROS 2/의존성 overlay가 준비된 환경에서 해당 프로젝트의 Python test runner로 실행한다. 환경에 따라 ROS/OpenSim native dependency가 필요할 수 있다.

## 하드웨어 확인

- OpenSim hardware-free 확인: `./scripts/run_opensim_live_link.ps1 -Test`
- wireless stack 후 pair/registry topic 확인
- fleet promotion gate: `python scripts/acceptance_gate.py`

실장비 테스트는 연결·캘리브레이션·recording 종료를 사람 눈으로 검증해야 한다. 자동화 test가 실제 보드나 native visualizer window의 물리적 동작을 대체하지 않는다.
