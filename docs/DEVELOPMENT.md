<!-- generated-by: gsd-doc-writer -->
# Development

## Studio 명령

`rehab-robotics-studio/package.json`의 명령입니다.

| 명령 | 설명 |
| --- | --- |
| `npm run dev` | Vite 개발 서버 |
| `npm run build` | TypeScript 검사 후 production build |
| `npm run typecheck` | TypeScript type check |
| `npm test` | `src/**/*.test.ts(x)` test 실행 |
| `npm run test:frequency-panel` | 주파수 패널 회귀 검사 |
| `npm run test:phase19` | Phase 19 GUI QA |
| `npm run test:gui-live` | live GUI E2E script |

## 변경 원칙

1. UI-only 변경은 `components/`에서 시작하되, 상태는 component local state보다 `state/` ownership을 우선 확인한다.
2. ROS topic/service를 바꾸면 `RosbridgeDataSource.ts`, backend node, 관련 test를 함께 바꾼다.
3. firmware protocol/packet 변경은 Master와 Slave sketch, `esp32_bridge_node.py`, `fleet_bridge_node.py`, relay를 함께 검토한다.
4. 변경 전후 `git status --short`를 확인한다. 이 저장소에는 다른 작업자의 미커밋 변경이 있을 수 있다.

## 코드 스타일

별도 formatter/linter 설정은 발견되지 않았다. 기존 TypeScript와 Python의 형식, type annotation, 명시적 constant 명명 방식을 따른다. 타이밍·port·주제(topic) 값은 매직 넘버 대신 이름 있는 상수에 둔다.

## 안전 관련 변경

OpenSim 제품 각도 gate, E-stop/runtime state transition, recording finalization, device identity 규약은 임의로 완화하지 않는다. 자세한 계약은 `opensim-ik-contracts.md`와 `stepesp-identity-identify.md`에 있다.
