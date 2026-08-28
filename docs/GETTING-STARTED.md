<!-- generated-by: gsd-doc-writer -->
# Getting Started

## 준비물

- Windows PowerShell, Python, Node.js/npm
- WSL `Ubuntu-22.04`, ROS 2 Humble
- OpenSim을 사용할 경우 프로젝트 제공 설정 스크립트와 인터넷 연결
- 실제 acquisition을 할 경우 ESP32 Master/Slave 및 해당 Wi-Fi profile

## GUI만 개발할 때

```powershell
cd rehab-robotics-studio
npm install
npm run dev
```

기본 data source는 rosbridge다. ROS가 없을 때 mock을 쓰려면 Vite 환경 변수 `VITE_DATA_SOURCE=mock`을 설정한다. 실제 source 선택 코드는 `src/data/appDataSource.ts`에 있다.

## 하드웨어 전체 스택

1. 인터넷이 되는 상태에서 필요한 경우 OpenSim 환경을 준비한다.

   ```powershell
   .\scripts\setup_opensim_live_link.ps1
   ```

2. Master를 먼저, Slave를 다음에 켠다.
3. 저장소 루트에서 `start_stepesp_wireless.ps1`을 실행한다.
4. `/esp/status/pair`과 `/esp/fleet/registry`로 연결을 확인하고 Studio에서 `Run`을 선택한다.
5. 종료 전 recording을 멈추고 `stop_stepesp_wireless.ps1`을 실행한다.

## 흔한 문제

- **GUI가 열리지 않음:** `rehab-robotics-studio/node_modules` 존재와 `logs/stepesp_gui.err.log`를 확인한다.
- **장치가 연결되지 않음:** SSID/IP 대신 canonical MAC identity와 `logs/stepesp_windows_relay*.log`를 확인한다.
- **OpenSim window가 없음:** `/opensim/status`의 reason과 `/home/justi/stepesp_opensim_bridge.log`를 확인한다.

다음 단계: [개발](DEVELOPMENT.md), [테스트](TESTING.md), [설정값 변경 지도](CODE-CHANGE-MAP.md).
