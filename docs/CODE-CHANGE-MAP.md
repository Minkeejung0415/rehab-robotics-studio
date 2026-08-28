# 코드 변경 지도

이 문서는 “무엇을 바꾸려면 어느 파일을 열어야 하는가”를 위한 유지보수 지도입니다. 코드 파일의 큰 기능 블록에도 같은 목적의 주석을 추가했습니다.

## 1. 전체 코드 구조

```text
firmware → scripts/relay → backend ROS 2 → rosbridge → Studio data → store → component
                         └────────────→ OpenSim IK ────────────────→ dashboard
```

| 하고 싶은 일 | 먼저 볼 곳 | 함께 확인할 곳 |
| --- | --- | --- |
| 화면 탭/레이아웃 변경 | `src/App.tsx`, `src/styles/app.css` | 해당 `components/` |
| 버튼 동작/실행 상태 변경 | `components/chrome/Toolbar.tsx` | `state/runtimeStore.ts`, `state/actions.ts` |
| 블록 종류·기본 파라미터 변경 | `graph/blockDefinitions.ts` | `graph/GraphModel.ts`, `components/canvas/BlockNode.tsx` |
| 센서 rate/range UI 변경 | `BlockNode.tsx`, `PropertiesPanel.tsx` | `appDataSource.ts`, `RosbridgeDataSource.ts`, firmware |
| ROS URL/topic/service 변경 | `data/RosbridgeDataSource.ts` | backend publisher/service와 test |
| mock 데이터 변경 | `data/MockDataSource.ts` | `types/signals.ts`, dashboard panels |
| runtime state/E-stop 규칙 변경 | `state/runtimeStore.ts` | Toolbar, `systemStore.ts` |
| mapping UI/서비스 변경 | `components/mapping/MappingWorkspace.tsx` | `state/mappingStore.ts`, `backend/.../mapping_node.py` |
| OpenSim IK/calibration 변경 | `backend/.../opensim_node.py`, `opensim/` | `data/liveKneeAngle.ts`, `HealthPanel.tsx` |
| device fleet/identity 변경 | `fleet_bridge_node.py`, `esp32_bridge_node.py` | `stepesp_tcp_udp_relay.py`, firmware |
| ESP32 network/recording 변경 | Master/Slave `.ino` | `start_stepesp_wireless.ps1`, bridge tests |

## 2. 시간·자동 동작 숫자 찾기

Studio의 프로젝트 `Save`는 수동 실행이지만, **하드웨어 SD recording에는 연결 끊김 후 자동 local-save/finalize 보호 동작이 이미 있습니다.** Host control 연결이 recording 중 끊기면 ESP32는 `host-disconnected-grace` 상태로 바뀌고 SD에 계속 기록합니다. 같은 control 연결이 grace 기간 안에 복구되면 `recording`으로 돌아갑니다. 기한이 끝나면 `disconnect_timeout`으로 finalization하며, Master는 Slave에도 `REC_STOP`을 relay해 각 SD card를 함께 마무리합니다.

현재 grace는 **90초(1분 30초)** 이며, 3분이 아닙니다. 이 값은 Master와 Slave 모두에서 동일하게 바꿔야 합니다.

이미 존재하는 시간값은 아래와 같습니다.

| 동작 | 숫자를 바꿀 위치 | 현재 값/의미 |
| --- | --- | --- |
| Toast 자동 닫힘 | `src/components/common/Toast.tsx` | `2500` ms |
| ROS service 응답 대기 | `src/data/RosbridgeDataSource.ts`의 `SERVICE_TIMEOUT_MS` | `10_000` ms |
| Identify UI 기본 timeout | `src/data/appDataSource.ts`, `RosbridgeDataSource.ts` | `5000` ms |
| Mock frame 주기 제한 | `src/data/MockDataSource.ts`의 `restart()` | 8–40 ms clamp |
| mapping reset UI 복구 | `components/mapping/MappingWorkspace.tsx` | `5000` ms |
| ESP Wi-Fi station 대기 | Master/Slave `.ino`의 `WIFI_STA_TIMEOUT_MS` | `30000` ms |
| ESP TCP idle client 종료 | Master/Slave `.ino`의 `TCP_IDLE_CLIENT_TIMEOUT_MS` | `30000` ms |
| 연결 끊김 뒤 SD local recording 유지 | Master/Slave `.ino`의 `REC_RECONNECT_GRACE_MS` | `90000` ms (90초) |
| SD 주기 flush | Master/Slave `.ino`의 `SD_PERIODIC_FLUSH_MS` | `1000` ms |
| ESP-NOW master sync timeout | Master/Slave `.ino`의 `MASTER_SYNC_TIMEOUT_MS` | `5000` ms |
| Visualizer input stale 기준 | launch의 `stale_timeout_s` | 기본 `1.0` s |

**주의:** firmware Master와 Slave에 같은 설정이 중복되어 있습니다. 통신·recording 동작값을 바꾸면 두 sketch를 같이 검토하고 관련 test를 실행합니다. Grace 동작 자체는 `recMarkControlDisconnected()`, `recMarkControlConnected()`, `recMaybeFinalizeTimeout()` 블록에 있습니다.

## 3. 설정 변경 순서

### Sample rate

1. UI 허용 범위/기본값: `graph/blockDefinitions.ts`, `BlockNode.tsx`, `PropertiesPanel.tsx`.
2. ROS request: `appDataSource.ts` → `RosbridgeDataSource.ts`.
3. Backend validation/control forwarding: `esp32_bridge_node.py`, `fleet_bridge_node.py`.
4. 실제 sample loop: Master/Slave firmware의 sample-rate control 및 loop.

UI 숫자만 바꾸면 하드웨어 범위와 불일치할 수 있으므로 위 경계를 모두 점검합니다.

### Wi-Fi, IP, 포트

일회성 실행 설정은 source edit보다 다음처럼 parameter로 전달합니다.

```powershell
.\scripts\start_stepesp_wireless.ps1 -WifiProfile '<SSID>' -MasterHost '<IP>' -MasterPort 5000
```

기본값 자체를 바꿔야 할 때만 `scripts/start_stepesp_wireless.ps1`의 param block을 수정합니다. firmware SSID/AP/port를 바꾸면 Master/Slave sketch의 `WIFI_*`, `TCP_PORT`, `WIFI_AP_*` 상수도 일치시킵니다.

### OpenSim 모델과 frame

- 기동 값: `start_stepesp_wireless.ps1`의 `OpenSimModel`, `OpenSimInstall`, `OpenSimEnvironment`.
- ROS launch 기본값: `backend/launch/*.launch.py`.
- mapping 가능한 frame 목록: `model_catalog_node.py`.
- IK 계약/안전 gate: `opensim/ik_contracts.py`, `opensim_node.py`.

## 4. 파일별 큰 역할

| 파일 | 책임 |
| --- | --- |
| `src/data/appDataSource.ts` | mock/ROS source 선택과 UI→hardware command facade |
| `src/data/RosbridgeDataSource.ts` | WebSocket protocol, topic subscribe, service call, parser |
| `src/state/runtimeStore.ts` | idle/running/paused/estop/fault transition |
| `src/state/systemStore.ts` | dashboard health/log/live data 상태 |
| `src/state/mappingStore.ts` | catalog, assignment, fleet registry 상태 |
| `backend/.../fleet_bridge_node.py` | N-device session, canonical topic, registry/alias |
| `backend/.../esp32_bridge_node.py` | legacy single-device bridge와 ESP control protocol |
| `backend/.../opensim_node.py` | ROS orchestration 및 joint state publish gate |
| `firmware/.../step_node.ino` | Master acquisition, radio, TCP/UDP, SD recording |
| `firmware/.../step_node_slave.ino` | Slave acquisition/ESP-NOW/SD counterpart |
| `scripts/start_stepesp_wireless.ps1` | Windows Wi-Fi, relay, WSL ROS, GUI 전체 기동 |

## 5. 변경 전 체크리스트

1. `git status --short`로 내 변경과 기존 변경을 구분한다.
2. topic/packet/parameter를 바꾸면 producer·consumer·test를 한 세트로 찾는다.
3. 시간값에는 단위를 이름에 포함한다(`*_MS`, `*_S`, `*_US`).
4. identity는 항상 canonical full-MAC으로 검증한다.
5. 하드웨어에 영향 있는 변경은 stop script로 종료·Wi-Fi 복구까지 확인한다.
