<!-- generated-by: gsd-doc-writer -->
# Architecture

이 프로젝트는 ESP32 센서 fleet에서 생성한 IMU/상태 데이터를 ROS 2로 수집하고, rosbridge를 통해 React Studio에 전달하는 계층형 시스템이다. OpenSim bridge는 같은 IMU 입력을 사용해 캘리브레이션된 IK 결과를 별도 제품 토픽으로 발행한다.

```text
ESP32 firmware
  → Windows TCP/UDP relay
  → ROS 2 fleet_bridge_node
  ├─ /esp/raw/*, /esp/status/*, /esp/fleet/registry
  ├─ mapping_node / model_catalog_node
  ├─ opensim_bridge → /opensim/joint_states
  └─ rosbridge_websocket (:9090)
       → RosbridgeDataSource
       → Zustand stores / signalBus
       → React Studio (:5173)
```

## 디렉터리 책임

| 경로 | 책임 |
| --- | --- |
| `rehab-robotics-studio/src/components` | 화면별 React component |
| `rehab-robotics-studio/src/data` | mock/ROS 입력, protocol parse, 데이터 경계 |
| `rehab-robotics-studio/src/state` | UI 및 runtime Zustand 상태 |
| `rehab-robotics-studio/src/graph` | 블록 정의, graph 검증·실행 모델 |
| `backend/rehab_robotics_bridge` | ROS 2 nodes와 ESP/OpenSim adapter |
| `backend/rehab_robotics_bridge/opensim` | calibration, IK contract, orientation IK |
| `firmware/step_node*` | ESP32 acquisition, network, SD, ESP-NOW |
| `scripts` | Windows↔WSL 운영 orchestration |

## 핵심 경계

- **UI 변경:** component → Zustand store/action → `appDataSource` 순으로 확인한다.
- **ROS message 변경:** `RosbridgeDataSource.ts` parser와 backend publisher를 동시에 변경하고 test를 보강한다.
- **제품 각도:** `/opensim/joint_states`만 사용한다. `/opensim/joint_angle`은 debug 전용이다.
- **장치 identity:** IP나 master/slave 문자열이 아니라 `esp32:<12 hex>` canonical ID를 key로 사용한다.

상세 변경 위치는 [CODE-CHANGE-MAP.md](CODE-CHANGE-MAP.md)에 정리되어 있다.
