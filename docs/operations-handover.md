# Rehab Robotics 운영 및 인수인계 문서

> 작성일: 2026-08-25  
> 목적: 소스 코드를 수정하지 않고도 다음 담당자가 시스템을 안전하게 시작·검증·종료하고, 문제 발생 시 담당 영역을 빠르게 좁힐 수 있도록 하는 운영 기준서입니다.

## 1. 시스템 한눈에 보기

```text
ESP32 Master / Slave(s)
  → Wi-Fi TCP/UDP
Windows TCP/UDP relay
  → WSL ROS 2 fleet_bridge_node
  → rosbridge (ws://127.0.0.1:9090)
  → React Studio (http://127.0.0.1:5173)
  → OpenSim bridge / model catalog / mapping / processing observer
```

- **GUI:** `rehab-robotics-studio/` — Vite + React/TypeScript.
- **ROS 2 backend:** `backend/` — ESP fleet bridge, ROS services, OpenSim 연동.
- **펌웨어:** `firmware/step_node/`, `firmware/step_node_slave/`.
- **주 운영 진입점:** `scripts/start_stepesp_wireless.ps1` 및 `scripts/stop_stepesp_wireless.ps1`.
- **안정적인 장치 식별자:** 역할명, DHCP IP가 아니라 `esp32:aabbccddeeff` 형식의 전체 base MAC.

## 2. 실행 전 인수인계 체크

새 담당자는 실제 실행 전에 아래 정보를 넘겨받아 기록합니다.

| 항목 | 넘겨받을 값 / 확인 방법 |
| --- | --- |
| 테스트 목적 | 단순 GUI 확인, 하드웨어 스트리밍, OpenSim IK, 녹화, 다중 센서 중 무엇인지 |
| 장치 목록 | Master와 각 Slave의 canonical ID (`esp32:<12 hex>`), 보드 역할, 펌웨어 버전 |
| 네트워크 | 실제 SSID, Windows Wi-Fi 어댑터 이름, Master IP/포트, Slave 연결 방식 |
| 런타임 | WSL 배포판(기본 `Ubuntu-22.04`), ROS install 경로, OpenSim environment/model 경로 |
| 현재 변경 사항 | `git status --short` 결과와 아직 커밋되지 않은 변경의 의도 |
| 실행 증적 | 최근 `logs/`와 WSL 로그, 마지막 정상/실패 시간, 재현 절차 |
| 안전 상태 | 녹화가 종료됐는지, 보드 전원 상태, 센서 부착/캘리브레이션 상태 |

### 현재 작업 트리 주의

2026-08-25 기준 작업 트리에는 OpenSim adapter/테스트, ESP32 펌웨어, GUI 속성 패널, 무선 시작 스크립트 등에 **미커밋 변경**이 있습니다. 또한 `rehab-robotics-studio/dist/`의 생성물 변경과 새 진단 스크립트도 있습니다. 인수인계받는 사람은 임의로 reset/checkout하지 말고, 소유자에게 변경 의도와 기준 커밋을 먼저 확인합니다.

## 3. Order of Operation — 표준 운영 순서

### A. 최초 1회 환경 준비 (인터넷 연결 상태)

1. Windows에서 Node.js/npm과 Python이 사용 가능한지 확인한다.
2. GUI 의존성이 없으면 `rehab-robotics-studio`에서 `npm install`을 한 번 실행한다.
3. WSL `Ubuntu-22.04`, ROS 2 Humble, `~/.rehab-install-v12/setup.bash`를 확인한다.
4. OpenSim live link를 처음 쓰거나 환경이 사라졌다면 저장소 루트에서 다음을 실행한다.

   ```powershell
   .\scripts\setup_opensim_live_link.ps1
   ```

5. 필요하면 하드웨어 없이 OpenSim 경로를 먼저 확인한다.

   ```powershell
   .\scripts\run_opensim_live_link.ps1 -Test
   ```

> OpenSim 설치는 네트워크가 필요한 작업일 수 있습니다. 하드웨어 AP/핫스팟으로 전환한 뒤에는 새 패키지 설치를 기대하지 않습니다.

### B. 하드웨어 기동

1. Master를 먼저 켜고 Slave를 켠다.
2. Master/Slave가 준비될 시간을 준다. Arduino Serial Monitor 등 제어 포트를 점유하는 프로그램은 닫는다.
3. 저장소 루트 PowerShell에서 현재 네트워크에 맞춰 시작한다.

   ```powershell
   .\scripts\start_stepesp_wireless.ps1
   ```

4. 장치 MAC을 알고 있다면 추측 기반 라우팅 대신 명시적으로 고정한다.

   ```powershell
   .\scripts\start_stepesp_wireless.ps1 `
     -ExpectedMasterDeviceId esp32:aabbccddeeff `
     -ExpectedSlaveDeviceId esp32:112233445566
   ```

5. 시작 스크립트가 GUI, Windows relay, WSL fleet bridge, rosbridge, processing observer, model catalog, mapping node, OpenSim bridge를 기동하고 `http://127.0.0.1:5173`을 연다.

### C. 연결 검증

아래 명령의 `RosInstall` 경로와 `ROS_DOMAIN_ID`는 시작 스크립트에 전달한 값과 일치해야 합니다(기본 domain은 `0`).

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ROS_DOMAIN_ID=0 ros2 topic echo /esp/status/pair --once --field data"
wsl -d Ubuntu-22.04 -- bash -lc "source /opt/ros/humble/setup.bash; source /home/justi/.rehab-install-v12/setup.bash; ROS_DOMAIN_ID=0 ros2 topic echo /esp/fleet/registry --once --field data"
```

계속 진행하려면 다음을 만족해야 합니다.

- pair 상태에서 master/slave가 `connected`이고 `pair_available: true`이다.
- registry에 기대한 full-MAC 장치만 보인다.
- GUI가 `ws://127.0.0.1:9090`에 연결되고 live 입력이 갱신된다.
- 장치가 둘 이상이면 각 장치의 canonical MAC 토픽과 호환 alias 토픽이 혼동되지 않는지 확인한다.

### D. Studio 및 OpenSim IK 운영

1. Studio에서 `Run`을 선택하고 입력/그래프가 갱신되는지 확인한다.
2. 필요하면 `Open visualizer`를 선택한다. 이는 OpenSim native window의 실행 요청이며, window가 정상 표시되는지는 사람이 눈으로 확인해야 한다.
3. 피험자가 무릎을 편 채로 안정 자세를 유지한 상태에서 `Calibrate`를 선택한다.
4. `Calibration state: CALIBRATED`와 `IK solution: Valid`가 된 뒤에만 각도 값을 사용한다.
5. Front Panel, Block Diagram, HealthPanel의 knee angle이 서로 같은지 확인한다.

**안전 게이트:** `UNCALIBRATED`, `CAPTURING`, `FAILED`, IK invalid, 혹은 2초 이상 stale 상태에서는 각도를 임상/제품 값으로 사용하지 않습니다. `/opensim/joint_angle`은 debug 전용이며 제품 IK 출력이 아닙니다. 제품 출력은 `/opensim/joint_states`입니다.

### E. 종료 순서

1. Studio에서 활성 녹화를 먼저 종료한다.
2. Studio에서 `Stop`을 선택한다.
3. PowerShell에서 전체 관리 프로세스와 네트워크 복구를 수행한다.

   ```powershell
   .\scripts\stop_stepesp_wireless.ps1
   ```

4. 정상 인터넷 프로필로 복귀했는지 확인한 뒤 보드 전원을 끈다.
5. 로그 경로, 장치 상태, 오류 여부를 인수인계 기록에 남긴다.

### Recording 연결 유실 보호

Recording 중 host control 연결이 끊겨도 ESP32는 즉시 SD 저장을 멈추지 않습니다. Master와 Slave firmware의 `REC_RECONNECT_GRACE_MS`가 현재 **90,000 ms (90초)** 동안 local SD recording을 계속 유지합니다. 이 시간 안에 control 연결이 복구되면 recording 상태로 되돌아가고, 복구되지 않으면 `disconnect_timeout`으로 finalization합니다. Master는 Slave에 stop을 relay합니다.

이 시간을 바꾸려면 Master와 Slave firmware 양쪽의 `REC_RECONNECT_GRACE_MS`를 같은 값으로 변경해야 합니다. `SD_PERIODIC_FLUSH_MS`는 별도로 1초마다 SD data/FAT size를 flush하는 전원 유실 보호 주기입니다.

## 4. 네트워크 및 기본값 — 반드시 실행 시 확인

기존 문서 일부는 `STEP_ESP32` / `192.168.4.1`을 예로 들지만, **현재** `start_stepesp_wireless.ps1`의 기본값은 아래와 같습니다.

| 파라미터 | 현재 기본값 |
| --- | --- |
| Wi-Fi profile | `iPhone (111)` |
| Master host | `172.20.10.3` |
| Master/Slave control port | `5000` |
| Master UDP port | `55001` |
| Windows relay ports | Master `5002`, 첫 Slave `5003` |
| rosbridge | `127.0.0.1:9090` |
| GUI | `127.0.0.1:5173` |
| WSL distro | `Ubuntu-22.04` |

따라서 실제 장비가 `STEP_ESP32` AP를 사용한다면, 실행 전에 현재 스크립트의 매개변수/네트워크를 확인하고 적절히 전달합니다. IP나 DHCP 순서만으로 장치를 식별해서는 안 됩니다.

## 5. 주요 토픽과 책임 경계

| 구분 | 주요 인터페이스 | 용도 |
| --- | --- | --- |
| Fleet 상태 | `/esp/fleet/registry` | 전체 장치의 권위 있는 inventory/상태 |
| 호환 pair 상태 | `/esp/status/pair` | Master/Slave alias 연결 확인 |
| 원시 역할 입력 | `/esp/raw/master`, `/esp/raw/slave` | GUI live 입력의 기본 source |
| IMU alias | `/esp32/master/imu`, `/esp32/slave/imu` | OpenSim 입력 기본값 |
| OpenSim 상태 | `/opensim/status`, `/opensim/ik_status` | 시각화/IK 상태와 실패 사유 |
| 제품 각도 | `/opensim/joint_states` | calibrated + valid IK일 때만 발행 |
| mapping | `/rehab/model/catalog`, `/rehab/mapping/current` | 모델 frame 목록과 적용 mapping |
| processing | `/processing_blocks/draft`, `/processing_blocks/update` | GUI processing block 변경 관찰 |

## 6. 장애 발생 시 우선순위

1. **GUI만 안 보임:** `logs/stepesp_gui.log`, `logs/stepesp_gui.err.log` 확인 → `http://127.0.0.1:5173`와 port 5173 충돌 확인.
2. **GUI는 열리지만 데이터 없음:** `/esp/status/pair`, `/esp/fleet/registry` 확인 → relay log와 fleet bridge log 확인.
3. **특정 Slave만 없음:** IP가 아니라 canonical ID와 identity inventory를 확인. 중복/미검증 identity는 fail-closed가 정상 동작이다.
4. **OpenSim/각도만 실패:** `/opensim/status`, `/opensim/ik_status`의 reason부터 확인 → 캘리브레이션·센서 freshness·model frame을 순서대로 확인.
5. **Visualizer window만 실패:** IK와 녹화의 즉각 중단 사유는 아닐 수 있다. OpenSim log를 확인하고 `Open visualizer` 재시도를 한다.
6. **종료/재시작이 꼬임:** 새 start를 반복하지 말고 stop script를 한 번 실행해 relay/WSL/GUI 프로세스와 Wi-Fi 상태를 정리한 후 재시작한다.

## 7. 로그 위치

| 범위 | 위치 |
| --- | --- |
| Windows relay | `logs/stepesp_windows_relay.log`, `logs/stepesp_windows_relay.err.log` |
| Windows serial diagnostics | `logs/stepesp_master_serial*.log`, `logs/stepesp_slave_serial*.log` |
| GUI | `logs/stepesp_gui.log`, `logs/stepesp_gui.err.log` |
| WSL fleet bridge | `/home/justi/stepesp_fleet_bridge.log` |
| rosbridge | `/home/justi/stepesp_rosbridge.log` |
| processing observer | `/home/justi/stepesp_processing_observer.log` |
| OpenSim bridge | `/home/justi/stepesp_opensim_bridge.log` |
| model catalog / mapping | `/home/justi/stepesp_model_catalog.log`, `/home/justi/stepesp_mapping.log` |

예시:

```powershell
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_fleet_bridge.log"
wsl -d Ubuntu-22.04 -- bash -lc "tail -80 /home/justi/stepesp_opensim_bridge.log"
```

## 8. 다음 담당자에게 남길 최소 기록 템플릿

```text
일시 / 담당자:
목적 및 수행 범위:
기준 commit / git status:
네트워크(SSID, adapter, Master IP):
Master canonical ID:
Slave canonical ID 목록:
펌웨어 버전 / 보드 revision:
실행 명령과 인자:
ROS_DOMAIN_ID / WSL distro:
검증 결과(pair, registry, GUI, IK, recording):
발생 오류 및 첫 오류 시각:
관련 로그 경로:
남은 작업 / 재현 절차 / 주의사항:
```

## 9. 관련 상세 문서

- [무선 스택 운영](./stepesp-wireless-setup.md)
- [장치 identity 및 Identify 안전 규약](./stepesp-identity-identify.md)
- [OpenSim quaternion live link](./opensim-quaternion-live-link.md)
- [OpenSim IK ROS 계약](./opensim-ik-contracts.md)
- [하드웨어 acceptance gate](./hardware-acceptance-report.md)
