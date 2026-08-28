<!-- generated-by: gsd-doc-writer -->
# Configuration

설정값은 용도별로 한 곳에서 관리해야 한다. 정확한 변경 위치는 [CODE-CHANGE-MAP.md](CODE-CHANGE-MAP.md)의 표를 우선한다.

| 영역 | 주 설정 위치 | 예시 |
| --- | --- | --- |
| Studio data source | `src/data/appDataSource.ts` | `VITE_DATA_SOURCE`, fallback source |
| Studio ROS topic/service/timeout | `src/data/RosbridgeDataSource.ts` | port 9090, service timeout, topic 이름 |
| Studio block 기본값 | `src/graph/blockDefinitions.ts` | sample rate, gain, IMU range |
| ROS launch | `backend/launch/rehab_robotics.launch.py` | host/port, rosbridge, OpenSim 옵션 |
| Windows 운영 | `scripts/start_stepesp_wireless.ps1` | SSID, master IP, WSL 경로, relay port |
| ESP32 firmware | `firmware/step_node/step_node.ino`, slave counterpart | Wi-Fi, AP, TCP, SD flush, sensor rate |

외부 환경(보드 IP, Wi-Fi profile, WSL 설치 경로)은 source 변경 대신 start script parameter로 우선 전달한다. 실제 장치 identity는 항상 full MAC을 사용한다.
