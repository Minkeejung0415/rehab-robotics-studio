# Rehab Robotics — Total Handoff Document

> 대상: 다음 개발자·운영자·연구 담당자  
> 범위: 시스템 구조, 실행/종료, 코드 변경 위치, 설정값, 장애 대응, SD 녹화 보호, 인수인계 기록

## 1. 절대 지켜야 할 규칙

1. 장치는 DHCP IP나 `master`/`slave` 이름이 아니라 `esp32:aabbccddeeff` 형식의 canonical full-MAC으로 식별한다.
2. 제품 knee angle은 `/opensim/joint_states`만 사용한다. `/opensim/joint_angle`은 debug 전용이다.
3. `CALIBRATED`와 valid IK가 아닐 때 knee angle을 제품/임상 값으로 사용하지 않는다.
4. firmware 통신·recording 설정은 Master와 Slave 양쪽을 같이 검토한다.
5. source 변경 전 `git status --short`를 확인한다. 현재 작업 트리에는 다른 작업의 미커밋 변경이 있을 수 있다.

## 2. 최초 환경 준비

필요 도구: Windows PowerShell, Python, Node.js/npm, WSL `Ubuntu-22.04`, ROS 2 Humble. OpenSim을 처음 사용하거나 환경이 사라졌다면 인터넷이 되는 상태에서 실행한다.

```powershell
.\scripts\setup_opensim_live_link.ps1
.\scripts\run_opensim_live_link.ps1 -Test
```

GUI 개발 의존성이 없다면:

```powershell
cd rehab-robotics-studio
npm install
```

GUI만 개발할 때 `VITE_DATA_SOURCE=mock`을 사용하면 ROS 없이 mock source를 쓸 수 있다. source 선택은 `src/data/appDataSource.ts`가 담당한다.

## 3. 표준 Order of Operation

### 시작

1. Master 전원을 먼저 켜고 Slave를 켠다. 제어 포트를 점유하는 Arduino Serial Monitor는 닫는다.
2. 저장소 루트 PowerShell에서 실행한다.

   ```powershell
   .\scripts\start_stepesp_wireless.ps1
   ```

3. 장치 identity를 알고 있으면 명시한다.

   ```powershell
   .\scripts\start_stepesp_wireless.ps1 `
     -ExpectedMasterDeviceId esp32:aabbccddeeff `
     -ExpectedSlaveDeviceId esp32:112233445566
   ```

4. script가 Windows relay, fleet bridge, rosbridge, processing observer, model catalog, mapping node, OpenSim bridge, GUI를 기동한다.
5. Studio에서 `Run`을 선택한다.

### 연결 확인

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ROS_DOMAIN_ID=0 ros2 topic echo /esp/status/pair --once --field data"
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ROS_DOMAIN_ID=0 ros2 topic echo /esp/fleet/registry --once --field data"
```

다음이 모두 맞아야 한다.

- pair의 master/slave가 `connected`, `pair_available: true`
- registry의 full-MAC 장치가 기대한 장치와 일치
- GUI가 `ws://127.0.0.1:9090`에 연결되어 live data 갱신

### OpenSim IK

1. Studio에서 필요 시 `Open visualizer`를 선택한다. native window 표시 자체는 사람이 확인한다.
2. 안정된 서 있는 자세에서 `Calibrate`를 선택한다.
3. `Calibration state: CALIBRATED`, `IK solution: Valid` 후에만 angle을 사용한다.
4. Front Panel, Block Diagram, HealthPanel의 knee 표시를 교차 확인한다.

### 종료

1. 녹화를 종료한다.
2. Studio에서 `Stop`을 선택한다.
3. 다음 script로 relay/WSL/GUI를 정리하고 인터넷 profile을 복원한다.

   ```powershell
   .\scripts\stop_stepesp_wireless.ps1
   ```

4. 로그와 장치 상태를 인수인계 기록에 남기고 보드 전원을 끈다.

## 4. 녹화와 인터넷/host 연결 유실 보호

이 기능은 Studio project Save가 아니라 **ESP32 SD recording 보호**다.

- 녹화 중 host control 연결이 끊기면 firmware는 `host-disconnected-grace`가 되고 SD에 계속 local recording한다.
- control 연결이 기한 안에 복구되면 `recording`으로 돌아간다.
- 현재 기한은 **90초** (`REC_RECONNECT_GRACE_MS 90000UL`)다.
- 기한 만료 시 `disconnect_timeout`으로 파일을 finalization한다.
- Master는 Slave에도 `REC_STOP`을 relay하여 양쪽 SD recording을 마무리한다.
- `SD_PERIODIC_FLUSH_MS`는 별도의 전원 유실 보호 flush 주기이며 현재 1초다.

값 변경 위치:

| 변경 대상 | Master | Slave |
| --- | --- | --- |
| 연결 유실 grace | `firmware/step_node/step_node.ino`의 `REC_RECONNECT_GRACE_MS` | `firmware/step_node_slave/step_node_slave.ino`의 같은 상수 |
| SD flush 주기 | `SD_PERIODIC_FLUSH_MS` | `SD_PERIODIC_FLUSH_MS` |

둘 중 한쪽만 바꾸면 pair recording 동작이 불일치할 수 있다.

## 5. 중요 설정값과 변경 위치

| 목적 | 위치 | 현재 값/주의 |
| --- | --- | --- |
| GUI rosbridge endpoint | `src/data/RosbridgeDataSource.ts` | 기본 `ws://127.0.0.1:9090` |
| ROS service UI timeout | 같은 파일 `SERVICE_TIMEOUT_MS` | `10_000` ms |
| Toast 자동 닫힘 | `src/components/common/Toast.tsx` | `2500` ms |
| Mock stream frame clamp | `src/data/MockDataSource.ts` | 8–40 ms, 실제 hardware rate 아님 |
| ESP pair UI rate/range | `graph/blockDefinitions.ts`, `BlockNode.tsx`, `PropertiesPanel.tsx` | backend/firmware 검증과 함께 변경 |
| Wi-Fi profile/Master host/relay port | `scripts/start_stepesp_wireless.ps1` param block | source 변경 전 parameter 전달을 우선 |
| ESP Wi-Fi/TCP | Master/Slave `.ino`의 `WIFI_*`, `WIFI_AP_*`, `TCP_PORT` | 양쪽 일치 필요 |
| Wi-Fi station timeout | Master/Slave `.ino`의 `WIFI_STA_TIMEOUT_MS` | `30000` ms |
| TCP idle timeout | Master/Slave `.ino`의 `TCP_IDLE_CLIENT_TIMEOUT_MS` | `30000` ms |
| OpenSim stale input | launch `stale_timeout_s` | 기본 `1.0` s |

현재 start script 기본값은 `iPhone (111)`, Master `172.20.10.3`, control port `5000`, relay master port `5002`, 첫 slave relay port `5003`, GUI `5173`, rosbridge `9090`이다. 이전 `STEP_ESP32`/`192.168.4.1` 문서 예시는 장비 topology에 따라 다를 수 있으므로 실행 script parameter를 기준으로 확인한다.

## 6. 코드 변경 지도

| 바꾸려는 것 | 시작 파일 | 함께 확인할 파일 |
| --- | --- | --- |
| 화면 탭/레이아웃 | `src/App.tsx`, `src/styles/app.css` | 해당 `components/` |
| toolbar/run/stop/save | `components/chrome/Toolbar.tsx` | `state/runtimeStore.ts`, `state/actions.ts` |
| runtime/E-stop state 규칙 | `state/runtimeStore.ts` | `systemStore.ts`, Toolbar |
| block 종류/기본값 | `graph/blockDefinitions.ts` | `GraphModel.ts`, `BlockNode.tsx` |
| graph 저장 포맷 | `graph/GraphModel.ts` | `state/graphStore.ts`, test |
| ROS topic/service/parser | `data/RosbridgeDataSource.ts` | backend publisher/service, test |
| mock data | `data/MockDataSource.ts` | `types/signals.ts`, dashboard |
| mapping UI | `components/mapping/MappingWorkspace.tsx` | `state/mappingStore.ts`, `mapping_node.py` |
| OpenSim calibration/IK | `opensim_node.py`, `opensim/` | `liveKneeAngle.ts`, `HealthPanel.tsx` |
| fleet/identity | `fleet_bridge_node.py`, `esp32_bridge_node.py` | relay, firmware |
| ESP packet/network/SD | Master/Slave `.ino` | bridge nodes, relay, firmware tests |

변경 시 data flow를 따라 producer와 consumer를 같이 바꾼다.

```text
firmware → relay → backend publisher → rosbridge parser → store → UI
```

## 7. 핵심 ROS 인터페이스

| 인터페이스 | 역할 |
| --- | --- |
| `/esp/fleet/registry` | N-device 권위 inventory와 readiness |
| `/esp/status/pair` | master/slave alias pair health |
| `/esp/raw/master`, `/esp/raw/slave` | GUI live input |
| `/esp32/master/imu`, `/esp32/slave/imu` | OpenSim 기본 IMU 입력 |
| `/opensim/status`, `/opensim/ik_status` | visualizer/IK 상태 및 reason |
| `/opensim/joint_states` | calibrated + valid IK 제품 output |
| `/rehab/model/catalog`, `/rehab/mapping/current` | model frame과 mapping 상태 |
| `/processing_blocks/draft`, `/processing_blocks/update` | processing block 변경 관찰 |

## 8. 장애 대응 순서

| 증상 | 첫 확인 | 다음 확인 |
| --- | --- | --- |
| GUI가 열리지 않음 | `logs/stepesp_gui.err.log`, port 5173 | npm/node_modules |
| GUI에 데이터 없음 | `/esp/status/pair`, `/esp/fleet/registry` | relay/fleet bridge log |
| 특정 Slave 없음 | canonical identity inventory | IP/DHCP 추측 금지 |
| OpenSim/angle 실패 | `/opensim/status`, `/opensim/ik_status` reason | calibration, freshness, model frame |
| visualizer만 실패 | OpenSim bridge log | IK/recording은 별도 상태 확인 |
| 재시작이 꼬임 | stop script 실행 | 이후 한 번만 start |

## 9. 로그 위치

| 범위 | 위치 |
| --- | --- |
| Windows relay | `logs/stepesp_windows_relay.log`, `logs/stepesp_windows_relay.err.log` |
| GUI | `logs/stepesp_gui.log`, `logs/stepesp_gui.err.log` |
| Windows serial diagnostics | `logs/stepesp_master_serial*.log`, `logs/stepesp_slave_serial*.log` |
| WSL fleet | `/home/justi/stepesp_fleet_bridge.log` |
| rosbridge | `/home/justi/stepesp_rosbridge.log` |
| processing observer | `/home/justi/stepesp_processing_observer.log` |
| OpenSim | `/home/justi/stepesp_opensim_bridge.log` |
| model catalog/mapping | `/home/justi/stepesp_model_catalog.log`, `/home/justi/stepesp_mapping.log` |

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_fleet_bridge.log"
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_opensim_bridge.log"
```

## 10. 테스트와 검증

```powershell
cd rehab-robotics-studio
npm run typecheck
npm test
npm run build
```

추가 확인:

```powershell
.\scripts\run_opensim_live_link.ps1 -Test
python scripts\acceptance_gate.py
```

실장비 연결, 센서 부착, native visualizer 표시, physical recording 결과는 자동 test만으로 확정할 수 없으므로 사람이 확인한다.

## 11. 인수인계 템플릿

```text
일시 / 담당자:
목적 및 수행 범위:
기준 commit / git status:
네트워크(SSID, Wi-Fi adapter, Master IP):
Master canonical ID:
Slave canonical ID 목록:
펌웨어 버전 / board revision:
실행 명령과 전달 인자:
ROS_DOMAIN_ID / WSL distro:
OpenSim model / frame 설정:
검증 결과(pair, registry, GUI, IK, recording):
연결 유실 recording grace 확인 여부:
발생 오류 및 첫 오류 시각:
관련 로그 경로:
남은 작업 / 재현 절차 / 주의사항:
```

## 12. 세부 참고 문서

- `operations-handover.md`: 운영 중심 runbook
- `CODE-CHANGE-MAP.md`: 파일별 변경 위치와 시간값 목록
- `stepesp-wireless-setup.md`: 무선 stack 상세
- `stepesp-identity-identify.md`: identity/identify 안전 규약
- `opensim-ik-contracts.md`: OpenSim IK topic 및 hard gate
- `hardware-acceptance-report.md`: hardware promotion evidence
