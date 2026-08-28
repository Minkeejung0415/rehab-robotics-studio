<!-- generated-by: gsd-doc-writer -->
# Rehab Robotics Studio

ESP32 기반 재활 로봇 센서 데이터를 ROS 2, OpenSim, React Studio로 연결하는 실험용 제어·시각화 시스템입니다.

## 구성

- `rehab-robotics-studio/`: 브라우저 기반 블록 다이어그램, 대시보드, 센서 매핑 UI
- `backend/`: ROS 2 bridge, fleet 관리, OpenSim IK 및 매핑 서비스
- `firmware/`: ESP32 Master/Slave 펌웨어
- `scripts/`: Windows/WSL 실행, relay, 진단 및 검증 도구

## 빠른 시작

하드웨어 무선 스택은 저장소 루트 PowerShell에서 시작합니다.

```powershell
.\scripts\start_stepesp_wireless.ps1
```

정상 기동 시 Studio는 `http://127.0.0.1:5173`, rosbridge는 `ws://127.0.0.1:9090`을 사용합니다. 종료할 때는 아래 스크립트로 관리 프로세스와 Wi-Fi 상태를 함께 복구합니다.

```powershell
.\scripts\stop_stepesp_wireless.ps1
```

개발 환경과 구조는 [시작 안내](docs/GETTING-STARTED.md), [구조](docs/ARCHITECTURE.md), [코드 변경 지도](docs/CODE-CHANGE-MAP.md)를 참고합니다.
