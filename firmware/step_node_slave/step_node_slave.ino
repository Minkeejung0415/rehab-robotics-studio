/*
 * STEP ESP32-S3 SLAVE node — Arduino IDE entry point
 * Seeed XIAO ESP32S3: ICM20948 + DIO + SD — records to SD, syncs clock via ESP-NOW from master.
 * Flash this to slave units. Master: esp32/arduino/step_node/step_node.ino
 *
 * Guide: docs/arduino-ide-guide.md
 *
 * --- Default Wi-Fi topology ---
 * Master starts Soft AP: SSID STEP_ESP32, pass step1234, IP 192.168.4.1.
 * This slave joins STEP_ESP32 by default and receives a DHCP address.
 * On your PC: join Wi-Fi "STEP_ESP32" (password step1234), then Open Ephys / TCP host 192.168.4.1:5000.
 *
 * --- WIRING_4WIRE_ICM + USB to PC (copy-paste preset) ---
 * #define ENABLE_TCP false
 * #define ENABLE_SERIAL_BENCH true
 * #define ENABLE_ESPNOW false
 * #define ENABLE_SD false
 * #define PIN_ICM_CS D3
 * --- end preset ---
 *
 * --- USB_OPEN_EPHYS_MODE (USB power + PC — Wi-Fi not required for Open Ephys) ---
 * Plugin Acq Board: host\run_usb_plugin_bridge.ps1 COM5  (or serial_tcp_bridge.py COM5 --plugin)
 *   → Open Ephys Node IP 127.0.0.1:5000 — NOT the ESP32 Wi-Fi IP; bridge speaks REDPITAYA/START.
 * Ephys Socket (no Plugin build): serial_tcp_bridge.py COM5 without --plugin.
 * Set USB_OPEN_EPHYS_MODE true below (or copy these defines):
 * #define ENABLE_TCP false
 * #define ENABLE_SERIAL_BENCH true
 * #define SERIAL_OUTPUT_BINARY true
 * #define ENABLE_ESPNOW false
 * #define ENABLE_SD false
 * --- end USB_OPEN_EPHYS_MODE ---
 */

#define ENABLE_ESPNOW true
#define ESPNOW_WIFI_CHANNEL 6   // Must match WIFI_AP_CHANNEL so slaves on STEP_ESP32 AP receive sync
#define ESPNOW_UNICAST true     // Use unicast to master MAC instead of broadcast (saves ~2-3 mA per TX burst)
#define STEP_PERFORMANCE_PROFILE 1  // 1=240 MHz high-rate lab profile, 0=80 MHz battery/100 Hz profile
#if STEP_PERFORMANCE_PROFILE
#define STEP_PROFILE_NAME "performance"
#define STEP_CPU_MHZ 240
#else
#define STEP_PROFILE_NAME "battery"
#define STEP_CPU_MHZ 80
#endif

#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiUdp.h>
#include <lwip/sockets.h>
#include <errno.h>
#include <lwip/tcp.h>
#if ENABLE_ESPNOW
#include <esp_now.h>
#include <esp_mac.h>
#include "esp_wifi.h"
#endif
#include <esp_timer.h>
#include <SD.h>
#include <SPI.h>
#include <math.h>
#include <stdarg.h>
#include <string.h>

extern "C" {
#include "vqf.h"
}

struct IdentityPacket;
struct IdentifyRequestPacket;
struct IdentifyAckPacket;

#define FIRMWARE_VERSION "1.8.0"
#define WIFI_HOSTNAME "step-esp32"
#define BOOT_CSV_DELAY_MS 5000
#define REPEAT_STATUS_SEC 10
#define BOOT_DIAGNOSTICS true

#define DIO_DEBOUNCE_MS 15   // stable toggle within ~20 ms @ 100 Hz

// Default network. Slaves join the same iPhone hotspot as the master.
#define WIFI_SSID "iPhone (111)"
#define WIFI_PASS "1234567890"

#define WIFI_FORCE_SOFT_AP false
#define WIFI_ALLOW_SOFT_AP_FALLBACK false  // slave must not create a competing STEP_ESP32/.1 AP

// Soft AP fallback after STA timeout (automatic — do not need to edit unless renaming lab AP)
#define WIFI_AP_SSID "STEP_ESP32"
#define WIFI_AP_PASS "step1234"
#define WIFI_AP_CHANNEL 6       // 2.4 GHz only — use 1, 6, or 11; explicit helps Windows join
#define WIFI_AP_MAX_CONN 8
#define WIFI_STA_TIMEOUT_MS 30000
// XIAO boards: high TX can desense the onboard antenna — try lower if STA/AP both fail
#define WIFI_TX_POWER_STA WIFI_POWER_8_5dBm
#define WIFI_TX_POWER_AP WIFI_POWER_8_5dBm

#define TCP_PORT 5000
#define TCP_IDLE_CLIENT_TIMEOUT_MS 30000UL
#define TCP_WRITE_TIMEOUT_MS 500UL
#define TCP_WRITE_FAILURE_LIMIT 3U
#define UDP_STREAM_PORT 55001
#define WIFI_STREAM_OVER_TCP false
#define SAMPLE_HZ_DEFAULT 100
#define NUM_CHANNELS 14

#define ICM_BANK2_GYRO_SMPLRT_DIV 0x00
#define ICM_BANK2_GYRO_CONFIG_1 0x01
#define ICM_BANK2_ODR_ALIGN_EN 0x09
#define ICM_BANK2_ACCEL_SMPLRT_DIV_1 0x10
#define ICM_BANK2_ACCEL_SMPLRT_DIV_2 0x11
#define ICM_BANK2_ACCEL_CONFIG_1 0x14

#define PIN_SPI_SCK D3    // GPIO4, HSPI SCK
#define PIN_SPI_MISO D5   // GPIO6, HSPI MISO (SDO)
#define PIN_SPI_MOSI D1   // GPIO2, HSPI MOSI (SDA)
#define PIN_ICM_CS D4     // GPIO5, ICM CS
#define PIN_DIO D0        // GPIO1; change if wired elsewhere

#define NODE_IS_MASTER false
#define ENABLE_SD true

// The official XIAO ESP32S3 variant maps its active-low user LED to GPIO 21.
// Do not define a fallback pin: unknown board targets must remain unsupported.
#if defined(ARDUINO_XIAO_ESP32S3)
#define STEPESP_IDENTIFY_LED_VERIFIED 1
#define STEPESP_IDENTIFY_LED_PIN GPIO_NUM_21
#define STEPESP_IDENTIFY_LED_ACTIVE_LEVEL LOW
#define STEPESP_IDENTIFY_LED_BOARD_REVISION "seeed-xiao-esp32s3"
#else
#define STEPESP_IDENTIFY_LED_VERIFIED 0
#define STEPESP_IDENTIFY_LED_BOARD_REVISION "unsupported"
#endif

// Slave streams via WiFi TCP to plugin (joins master AP); no USB bridge needed.
#ifndef USB_OPEN_EPHYS_MODE
#define USB_OPEN_EPHYS_MODE false
#endif

#if USB_OPEN_EPHYS_MODE
#define ENABLE_TCP false
#define ENABLE_SERIAL_BENCH true
#define SERIAL_OUTPUT_BINARY true
#else
#define ENABLE_TCP true
#define ENABLE_SERIAL_BENCH false
#define SERIAL_OUTPUT_BINARY false
#endif


#define PIN_SD_CS 21

static SPIClass ICM_SPI(HSPI);

#define ICM_REG_BANK_SEL 0x7F
#define ICM_WHO_AM_I 0x00
#define ICM_PWR_MGMT_1 0x06
#define ICM_USER_CTRL 0x03
#define ICM_INT_PIN_CFG 0x0F
#define ICM_ACCEL_XOUT_H 0x2D
#define ICM20948_WHOAMI_VAL 0xEA
#define ICM_EXT_SENS_DATA_00 0x3B
#define ICM_I2C_MST_CTRL 0x01
#define ICM_I2C_SLV0_ADDR 0x03
#define ICM_I2C_SLV0_REG 0x04
#define ICM_I2C_SLV0_CTRL 0x05
#define ICM_I2C_SLV0_DO 0x06

#define AK09916_ADDR 0x0C
#define AK09916_WIA2 0x01
#define AK09916_ST1 0x10
#define AK09916_HXL 0x11
#define AK09916_ST2 0x18
#define AK09916_CNTL2 0x31
#define AK09916_CNTL3 0x32
#define AK09916_WIA2_VAL 0x09
#define AK09916_MODE_CONT_100HZ 0x08

#pragma pack(push, 1)
struct OeHeader {
  int32_t offset;
  int32_t num_bytes;
  uint16_t bit_depth;
  int32_t element_size;
  int32_t num_channels;
  int32_t samples_per_channel;
};
#pragma pack(pop)

#pragma pack(push, 1)
struct SdLogHeader {
  uint32_t magic;
  uint16_t version;
  uint16_t record_size;
  uint16_t sample_hz;
  uint16_t channel_count;
  int64_t start_time_us;
  uint16_t header_size;
  uint16_t flags;
  int64_t scheduled_start_time_us;
  int64_t scheduled_stop_time_us;
  int64_t clock_offset_us;
  uint8_t node_role;
  uint8_t sync_valid;
  uint16_t reserved;
};

struct SdLogRecord {
  uint32_t seq;
  uint32_t sample_index;
  int64_t time_us;
  int16_t ch[NUM_CHANNELS];
};

struct StreamRecord {
  OeHeader header;
  int16_t ch[NUM_CHANNELS];
  uint32_t seq;
};
#pragma pack(pop)

#define SD_LOG_MAGIC 0x31505453UL  // "STP1" little-endian
#define SD_LOG_VERSION 2
#define SD_LOG_FLAG_SCHEDULED 0x0001u
#define SD_LOG_ROLE_MASTER 1u
#define SD_LOG_ROLE_SLAVE 2u
#define REC_RECONNECT_GRACE_MS 90000UL
#define SD_QUEUE_DEPTH 1024
#define SD_WRITE_BATCH_RECORDS 256
#define SD_PERIODIC_FLUSH_MS 1000  // commit data + FAT size every 1 s so power loss costs <=1 s, not the whole file
#define MASTER_SYNC_TIMEOUT_MS 5000UL  // master ESP-NOW quiet longer than this arms the reconnect grace
#define STREAM_QUEUE_DEPTH 16
#define SD_TASK_PRIORITY 4
#define STREAM_TASK_PRIORITY 1
#define REC_MAX_CHUNK 1024UL
#define SDRF_HEADER_LEN 64
#define SDRF_TYPE_DATA 0x01
#define SDRF_TYPE_EOF 0x02

#pragma pack(push, 1)
struct SdrfHeader {
  char magic[4];
  uint8_t frame_version;
  uint8_t frame_type;
  uint16_t header_length;
  uint8_t session_id[16];
  uint32_t chunk_index;
  uint64_t byte_offset;
  uint32_t payload_length;
  uint64_t total_file_size;
  uint32_t header_crc32;
  uint32_t payload_checksum;
  uint32_t flags;
  uint32_t reserved;
};
#pragma pack(pop)

WiFiServer server(TCP_PORT);
WiFiClient client;
static uint32_t tcp_client_last_activity_ms = 0;
static volatile uint32_t g_tcp_consecutive_write_failures = 0;
static volatile bool g_tcp_reset_requested = false;
static uint8_t g_tcp_silent_accepts = 0;
static char g_cached_route_ip[16] = "0.0.0.0";
WiFiUDP stream_udp;
bool streaming = false;
bool wifi_up = false;
bool wifi_soft_ap = false;

static void cacheWifiRouteIp() {
  const IPAddress ip = wifi_soft_ap ? WiFi.softAPIP() : WiFi.localIP();
  snprintf(g_cached_route_ip, sizeof(g_cached_route_ip), "%u.%u.%u.%u",
           ip[0], ip[1], ip[2], ip[3]);
}

static void markWifiUp() {
  wifi_up = true;
  cacheWifiRouteIp();
}

uint32_t seq = 0;
int16_t channels[NUM_CHANNELS];
bool icm_ok = false;
bool mag_ok = false;
uint32_t boot_ms = 0;
bool csv_banner_sent = false;
uint32_t last_status_ms = 0;

// DIO input is included in the 14-channel OE stream.
struct {
  bool stable_high;
  bool pending_raw;
  uint32_t pending_since_ms;
  uint16_t edge_count;
} dio_state = {true, true, 0, 0};

static uint16_t g_sample_hz = SAMPLE_HZ_DEFAULT;
static uint32_t g_sample_last_us = 0;
static uint8_t g_acc_preset = 0;
static uint8_t g_gyr_preset = 0;
static bool g_filter_on = true;

static bool g_sd_ready = false;
static bool g_sd_recording = false;
static File g_sd_file;
static uint64_t g_generated_samples = 0;
static uint64_t g_sd_saved_samples = 0;
static uint64_t g_sd_write_errors = 0;
static uint64_t g_sd_queue_drops = 0;
static uint64_t g_sd_header_errors = 0;
static uint64_t g_sd_open_errors = 0;
static uint64_t g_sd_begin_errors = 0;
static uint64_t g_sd_mutex_timeouts = 0;
static uint64_t g_sd_flush_count = 0;
static uint32_t g_max_sd_write_us = 0;
static uint32_t g_max_sd_flush_us = 0;
static uint32_t g_sd_queue_max_depth = 0;
static uint32_t g_max_loop_us = 0;
static uint32_t g_loop_overruns = 0;
static uint64_t g_spi_mutex_timeouts = 0;
static uint64_t g_stream_offered = 0;
static uint64_t g_stream_enqueued = 0;
static uint64_t g_stream_sent = 0;
static uint64_t g_stream_queue_drops = 0;
static uint64_t g_stream_send_errors = 0;
static uint32_t g_stream_queue_max_depth = 0;
static uint32_t g_max_stream_send_us = 0;
static volatile uint32_t g_stream_target_ip = 0;
static uint64_t g_prof_samples = 0;
static uint64_t g_prof_imu_sum_us = 0;
static uint64_t g_prof_mag_sum_us = 0;
static uint64_t g_prof_vqf_sum_us = 0;
static uint64_t g_prof_vqf_mag_sum_us = 0;
static uint64_t g_prof_quat_sum_us = 0;
static uint64_t g_prof_serial_sum_us = 0;
static uint32_t g_prof_imu_max_us = 0;
static uint32_t g_prof_mag_max_us = 0;
static uint32_t g_prof_vqf_max_us = 0;
static uint32_t g_prof_vqf_mag_max_us = 0;
static uint32_t g_prof_quat_max_us = 0;
static uint32_t g_prof_serial_max_us = 0;
#if ENABLE_ESPNOW
static int64_t           g_clock_offset_us        = 0;
static bool              g_espnow_sync_received   = false;
static uint32_t          g_espnow_last_seq        = 0;
static volatile uint32_t g_espnow_last_rx_ms      = 0;  // last time any master packet arrived
static volatile bool     g_espnow_rec_start_pending = false;
static volatile bool     g_espnow_rec_stop_pending  = false;
static char              g_espnow_requested_session[33] = {};
static volatile int64_t  g_espnow_requested_start_at_us = 0;
static volatile int64_t  g_espnow_requested_stop_at_us = 0;
#if ESPNOW_UNICAST
static uint8_t           g_master_mac[6]          = {};
static bool              g_master_peer_registered = false;
#endif
#endif
static char g_sd_path[48] = "/step_session.bin";
static char g_rec_session_id[33] = "none";
static char g_rec_state[32] = "idle";
static char g_transfer_state[16] = "none";
static char g_finalization_reason[32] = "none";
static char g_last_rec_error[32] = "none";
static char g_last_schedule_error[32] = "none";
static uint64_t g_final_file_size = 0;
static uint32_t g_final_file_checksum = 0;
static uint32_t g_rec_grace_deadline_ms = 0;
static bool g_transfer_active = false;
static bool g_rec_schedule_enabled = false;
static bool g_rec_armed = false;
static int64_t g_rec_start_at_us = 0;
static int64_t g_rec_stop_at_us = 0;
static uint32_t g_sd_record_sample_index = 0;
static int64_t g_sd_header_start_time_us = 0;

static QueueHandle_t g_sd_queue = nullptr;
static QueueHandle_t g_stream_queue = nullptr;
static SemaphoreHandle_t g_sd_mutex = nullptr;
static SemaphoreHandle_t g_spi_mutex = nullptr;
static SemaphoreHandle_t g_tcp_mutex = nullptr;

static void configureTcpClient(WiFiClient &tcp_client) {
  tcp_client.setNoDelay(true);
  tcp_client.setTimeout(TCP_WRITE_TIMEOUT_MS);
  int enabled = 1;
  int idle_s = 3;
  int interval_s = 1;
  int probes = 3;
  tcp_client.setSocketOption(SOL_SOCKET, SO_KEEPALIVE, &enabled, sizeof(enabled));
  tcp_client.setSocketOption(IPPROTO_TCP, TCP_KEEPIDLE, &idle_s, sizeof(idle_s));
  tcp_client.setSocketOption(IPPROTO_TCP, TCP_KEEPINTVL, &interval_s, sizeof(interval_s));
  tcp_client.setSocketOption(IPPROTO_TCP, TCP_KEEPCNT, &probes, sizeof(probes));
}

static bool tcpPeerClosed(const WiFiClient &tcp_client) {
  const int fd = tcp_client.fd();
  if (fd < 0) {
    return true;
  }
  uint8_t peek = 0;
  const int n = recv(fd, &peek, 1, MSG_DONTWAIT | MSG_PEEK);
  return n == 0;
}

static bool tcpWriteBytes(const uint8_t *data, size_t len, uint32_t timeout_ms) {
  if (!g_tcp_mutex ||
      xSemaphoreTake(g_tcp_mutex, pdMS_TO_TICKS(timeout_ms)) != pdTRUE) {
    return false;
  }
  bool ok = false;
  const int sock = client.fd();
  if (sock >= 0) {
    size_t sent = 0;
    const uint32_t deadline = millis() + timeout_ms;
    while (sent < len && millis() < deadline) {
      const int n = send(sock, data + sent, len - sent, 0);
      if (n > 0) {
        sent += (size_t)n;
      } else if (n < 0 && (errno == EAGAIN || errno == EWOULDBLOCK)) {
        delay(1);
      } else {
        break;
      }
    }
    ok = sent == len;
  }
  xSemaphoreGive(g_tcp_mutex);
  return ok;
}

static void stopTcpClient() {
  if (!g_tcp_mutex ||
      xSemaphoreTake(g_tcp_mutex, pdMS_TO_TICKS(TCP_WRITE_TIMEOUT_MS)) != pdTRUE) {
    g_tcp_reset_requested = true;
    return;
  }
  client.stop();
  g_tcp_consecutive_write_failures = 0;
  g_tcp_reset_requested = false;
  xSemaphoreGive(g_tcp_mutex);
}

static void resetTcpListener() {
  stopTcpClient();
  server.end();
  delay(5);
  server.begin();
  tcp_client_last_activity_ms = 0;
  g_stream_target_ip = 0;
}

static const float kAccLsbPerG[4] = {16384.0f, 8192.0f, 4096.0f, 2048.0f};
static const float kGyrLsbPerDps[4] = {131.072f, 65.536f, 32.768f, 16.384f};
static const float kStdGravityMps2 = 9.80665f;
static const float kMagUnitsPerLsb = 0.15f;  // AK09916, matches Plugin sensor_fusion ICM20948
static const float kMagRateHz = 100.0f;
static const uint32_t kMagPollPeriodUs = 10000UL;
static const uint32_t kIcmSpiHz = 4000000UL;
static const uint8_t kIcmGyroSmplrtDiv = 0;
static const uint16_t kIcmAccelSmplrtDiv = 0;
static const uint8_t kIcmDlpfCfg = 0;
static const bool kIcmDlpfEnabled = false;

static VQF g_vqf;
static bool g_vqf_inited = false;
static int16_t g_last_mag[3] = {0, 0, 0};
static uint32_t g_last_mag_poll_us = 0;
static bool g_have_mag = false;

static bool useWifi() { return ENABLE_TCP; }

static uint64_t sdErrorTotal() {
  return g_sd_queue_drops + g_sd_write_errors + g_sd_header_errors +
         g_sd_open_errors + g_sd_begin_errors + g_sd_mutex_timeouts;
}

static void profAdd(uint32_t elapsed_us, uint64_t *sum_us, uint32_t *max_us) {
  *sum_us += elapsed_us;
  if (elapsed_us > *max_us) *max_us = elapsed_us;
}

static uint32_t profAvg(uint64_t sum_us) {
  if (g_prof_samples == 0) return 0;
  return (uint32_t)(sum_us / g_prof_samples);
}

static void profReset() {
  g_prof_samples = 0;
  g_prof_imu_sum_us = 0;
  g_prof_mag_sum_us = 0;
  g_prof_vqf_sum_us = 0;
  g_prof_vqf_mag_sum_us = 0;
  g_prof_quat_sum_us = 0;
  g_prof_serial_sum_us = 0;
  g_prof_imu_max_us = 0;
  g_prof_mag_max_us = 0;
  g_prof_vqf_max_us = 0;
  g_prof_vqf_mag_max_us = 0;
  g_prof_quat_max_us = 0;
  g_prof_serial_max_us = 0;
  g_spi_mutex_timeouts = 0;
}

static uint8_t icmConfig1(uint8_t fs_sel) {
  const uint8_t fchoice = kIcmDlpfEnabled ? 1u : 0u;
  return (uint8_t)(((kIcmDlpfCfg & 0x07u) << 3) | ((fs_sel & 0x03u) << 1) | fchoice);
}

static int16_t floatToQ15(float v) {
  if (v > 1.0f) v = 1.0f;
  if (v < -1.0f) v = -1.0f;
  return (int16_t)(v * 32767.0f);
}

static void icmApplyRangePresets() {
  if (!icm_ok) return;
  const uint8_t acc_fs = g_acc_preset & 3u;
  const uint8_t gyr_fs = g_gyr_preset & 3u;
  icmSelectBank(0, 2);
  icmWrite(ICM_BANK2_ACCEL_CONFIG_1, icmConfig1(acc_fs));
  icmWrite(ICM_BANK2_GYRO_CONFIG_1, icmConfig1(gyr_fs));
  icmSelectBank(0, 0);
#if !SERIAL_OUTPUT_BINARY
  Serial.printf("ICM range: ACC preset %u  GYR preset %u\n", acc_fs, gyr_fs);
#endif
}

static void icmConfigureOutputRate() {
  icmSelectBank(0, 2);
  icmWrite(ICM_BANK2_GYRO_SMPLRT_DIV, kIcmGyroSmplrtDiv);
  icmWrite(ICM_BANK2_ACCEL_SMPLRT_DIV_1, (uint8_t)(kIcmAccelSmplrtDiv >> 8));
  icmWrite(ICM_BANK2_ACCEL_SMPLRT_DIV_2, (uint8_t)(kIcmAccelSmplrtDiv & 0xFF));
  icmWrite(ICM_BANK2_ODR_ALIGN_EN, 0x01);
  icmSelectBank(0, 0);
}

static void vqfReinitFilter() {
  const float hz = (float)g_sample_hz;
  if (hz < 1.0f) return;
  const float imu_ts = 1.0f / hz;
  const float mag_ts = 1.0f / kMagRateHz;
  vqf_init(&g_vqf, imu_ts, imu_ts, mag_ts);
  g_vqf_inited = true;
}

static void imuRawToVqfPhysical(const int16_t imu[6], vqf_real_t acc[3], vqf_real_t gyr[3]) {
  const float acc_mps2_per_lsb =
      kStdGravityMps2 / kAccLsbPerG[g_acc_preset & 3u];
  const float gyr_rads_per_lsb =
      (float)(M_PI / 180.0) / kGyrLsbPerDps[g_gyr_preset & 3u];
  acc[0] = (vqf_real_t)((float)imu[0] * acc_mps2_per_lsb);
  acc[1] = (vqf_real_t)((float)imu[1] * acc_mps2_per_lsb);
  acc[2] = (vqf_real_t)((float)imu[2] * acc_mps2_per_lsb);
  gyr[0] = (vqf_real_t)((float)imu[3] * gyr_rads_per_lsb);
  gyr[1] = (vqf_real_t)((float)imu[4] * gyr_rads_per_lsb);
  gyr[2] = (vqf_real_t)((float)imu[5] * gyr_rads_per_lsb);
}

static void vqfUpdateFromImu(const int16_t imu[6], const int16_t *mag_or_null,
                             bool mag_fresh) {
  if (!g_vqf_inited)
    vqfReinitFilter();

  vqf_real_t acc[3], gyr[3];
  imuRawToVqfPhysical(imu, acc, gyr);
  uint32_t prof_start_us = micros();
  vqf_update(&g_vqf, gyr, acc);
  profAdd((uint32_t)(micros() - prof_start_us), &g_prof_vqf_sum_us, &g_prof_vqf_max_us);

  if (mag_or_null != nullptr && mag_fresh) {
    vqf_real_t mag[3];
    mag[0] = (vqf_real_t)((float)mag_or_null[0] * kMagUnitsPerLsb);
    mag[1] = (vqf_real_t)((float)mag_or_null[1] * kMagUnitsPerLsb);
    mag[2] = (vqf_real_t)((float)mag_or_null[2] * kMagUnitsPerLsb);
    prof_start_us = micros();
    vqf_update_mag(&g_vqf, mag);
    profAdd((uint32_t)(micros() - prof_start_us), &g_prof_vqf_mag_sum_us,
            &g_prof_vqf_mag_max_us);
  }
}

static void vqfReadQuatQ15(int16_t out[4], bool use_9d) {
  vqf_real_t quat[4];
  uint32_t prof_start_us = micros();
  if (use_9d)
    vqf_get_quat_9d(&g_vqf, quat);
  else
    vqf_get_quat_6d(&g_vqf, quat);
  profAdd((uint32_t)(micros() - prof_start_us), &g_prof_quat_sum_us,
          &g_prof_quat_max_us);
  out[0] = floatToQ15((float)quat[0]);
  out[1] = floatToQ15((float)quat[1]);
  out[2] = floatToQ15((float)quat[2]);
  out[3] = floatToQ15((float)quat[3]);
}

static void packChannelsFromImu(const int16_t imu[6], const int16_t *mag_or_null,
                                bool mag_fresh) {
  channels[0] = imu[0];
  channels[1] = imu[1];
  channels[2] = imu[2];
  channels[3] = imu[3];
  channels[4] = imu[4];
  channels[5] = imu[5];
  channels[6] = mag_or_null != nullptr ? mag_or_null[0] : 0;
  channels[7] = mag_or_null != nullptr ? mag_or_null[1] : 0;
  channels[8] = mag_or_null != nullptr ? mag_or_null[2] : 0;
  channels[9] = 0;
  channels[10] = 0;
  channels[11] = 0;
  channels[12] = 0;
  channels[13] = packDioCh6();

  if (!g_filter_on)
    return;

  vqfUpdateFromImu(imu, mag_or_null, mag_fresh);
  vqfReadQuatQ15(&channels[9], mag_or_null != nullptr && g_have_mag);
}

static int parseFreqHz(const String &line) {
  int idx = line.indexOf(':');
  String tail = (idx >= 0) ? line.substring(idx + 1) : line.substring(4);
  tail.trim();
  return tail.toInt();
}

static bool sampleHzValid(int hz) {
  return hz >= 1 && hz <= 65535;
}

static void applySampleRateHz(int hz) {
  if (!sampleHzValid(hz))
    return;
  g_sample_hz = (uint16_t)hz;
  g_sample_last_us = 0;
  g_loop_overruns = 0;
  g_max_loop_us = 0;
  profReset();
  if (g_filter_on)
    vqfReinitFilter();
}

static bool handleCfgLine(const String &line) {
  if (!line.startsWith("CFG ")) return false;
  int si = -1, preset = -1;
  char kind[8] = {};
  if (sscanf(line.c_str(), "CFG %d %7s %d", &si, kind, &preset) < 3) return false;
  if (si != 0) {
    replyToHost("ERROR CFG: sensor index must be 0 on ESP32 node\n");
    return true;
  }
  if (strncmp(kind, "ACC", 3) == 0) {
    g_acc_preset = (uint8_t)constrain(preset, 0, 3);
    icmApplyRangePresets();
    replyToHost("OK CFG ACC\n");
    return true;
  }
  if (strncmp(kind, "GYR", 3) == 0) {
    g_gyr_preset = (uint8_t)constrain(preset, 0, 3);
    icmApplyRangePresets();
    replyToHost("OK CFG GYR\n");
    return true;
  }
  if (strncmp(kind, "SRATE", 5) == 0) {
    if (!sampleHzValid(preset)) {
      replyToHost("ERROR CFG: SRATE Hz must be >= 1\n");
      return true;
    }
    int hz = preset;
    applySampleRateHz(hz);
    char buf[48];
    snprintf(buf, sizeof(buf), "OK FREQ:%d\n", hz);
    replyToHost(buf);
    return true;
  }
  replyToHost("ERROR CFG: unknown field\n");
  return true;
}

typedef struct {
  uint32_t seq;
  int64_t time_us;
} SyncPacket;

#define CMD_MAGIC        0xCB
#define CMD_START_STREAM 0x01
#define CMD_STOP_STREAM  0x02
#define CMD_REC_START    0x03
#define CMD_REC_STOP     0x04
#define CMD_SET_FREQ     0x05
#define CMD_FILTER_ON    0x06
#define CMD_FILTER_OFF   0x07
#define CMD_SET_CFG      0x08
#define CMD_SESSION_ID_LEN 32
#define CMD_PACKET_VERSION 2
#define CMD_FLAG_SCHEDULED 0x01
#define REC_SCHEDULE_GUARD_US 1000000LL
#define REC_SCHEDULE_MIN_LEAD_US 200000LL
#define SLAVE_STATUS_MAGIC 0x5A
#define SLAVE_STATUS_VERSION 2
#define IDENTITY_PACKET_MAGIC 0xD7
#define IDENTITY_PACKET_TYPE 0x01
#define IDENTITY_PACKET_VERSION 1
#define IDENTITY_ROLE_MASTER 1
#define IDENTITY_ROLE_SLAVE 2
#define IDENTITY_CAP_IDENTIFY 0x0001u
#define IDENTITY_STATUS_INTERVAL_MS 1000UL
#define IDENTIFY_PACKET_MAGIC 0xD8
#define IDENTIFY_REQUEST_TYPE 0x01
#define IDENTIFY_ACK_TYPE 0x02
#define IDENTIFY_PACKET_VERSION 1
#define IDENTIFY_COMMAND_ID_MAX 32
#define IDENTIFY_DURATION_MIN_MS 1000UL
#define IDENTIFY_DURATION_MAX_MS 5000UL
#define IDENTIFY_DURATION_DEFAULT_MS 3000UL
#define IDENTIFY_ACK_TIMEOUT_MS 1500UL
#define IDENTIFY_BLINK_INTERVAL_MS 200UL
#define IDENTIFY_OUTCOME_CONFIRMED 1
#define IDENTIFY_OUTCOME_SENT_UNCONFIRMED 2
#define IDENTIFY_OUTCOME_TIMEOUT 3
#define IDENTIFY_OUTCOME_OFFLINE 4
#define IDENTIFY_OUTCOME_UNSUPPORTED 5
#define IDENTIFY_OUTCOME_REJECTED 6
#define IDENTIFY_OUTCOME_INVALID_TARGET 7
#define SLAVE_STATUS_INTERVAL_MS 10UL
#define SLAVE_STATIC_IP_OCTET 0
#define SLAVE_REC_STATE_IDLE 0u
#define SLAVE_REC_STATE_ARMED 1u
#define SLAVE_REC_STATE_RECORDING 2u
#define SLAVE_REC_STATE_FINALIZING 3u
#define SLAVE_REC_STATE_FINALIZED 4u
#define SLAVE_REC_STATE_ERROR 5u
#define SLAVE_SCHEDULE_ERROR_NONE 0u
#define SLAVE_SCHEDULE_ERROR_UNSYNCED_START 1u
#define SLAVE_SCHEDULE_ERROR_LATE_START 2u
#define SLAVE_SCHEDULE_ERROR_SD_START_FAILED 3u

#pragma pack(push, 1)
struct CmdPacket {
  uint8_t magic;
  uint8_t cmd;
  uint8_t version;
  uint8_t flags;
  int64_t start_at_time_us;
  int64_t stop_at_time_us;
  char session_id[CMD_SESSION_ID_LEN + 1];
};
struct FreqCmdPacket {
  uint8_t magic;
  uint8_t cmd;
  uint16_t sample_hz;
};
struct CfgCmdPacket {
  uint8_t magic;
  uint8_t cmd;
  uint8_t kind;
  uint8_t preset;
};

struct IdentityPacket {
  uint8_t magic;
  uint8_t type;
  uint8_t version;
  uint16_t packet_size;
  uint8_t base_mac[6];
  uint8_t sta_mac[6];
  uint8_t ap_mac[6];
  uint8_t espnow_mac[6];
  uint8_t role;
  uint16_t capabilities;
  uint8_t verified;
  uint8_t reserved;
};

struct IdentifyRequestPacket {
  uint8_t magic;
  uint8_t type;
  uint8_t version;
  uint16_t packet_size;
  char command_id[IDENTIFY_COMMAND_ID_MAX + 1];
  uint8_t target_mac[6];
  uint32_t requested_duration_ms;
};

struct IdentifyAckPacket {
  uint8_t magic;
  uint8_t type;
  uint8_t version;
  uint16_t packet_size;
  char command_id[IDENTIFY_COMMAND_ID_MAX + 1];
  uint8_t target_mac[6];
  uint32_t requested_duration_ms;
  uint32_t applied_duration_ms;
  uint8_t outcome;
  uint8_t reserved[3];
};

struct SlaveStatusPacket {
  uint8_t magic;
  uint8_t version;
  uint16_t packet_size;
  uint32_t slave_id;
  uint8_t sd_ready;
  uint8_t sd_recording;
  uint8_t streaming;
  uint8_t sync_received;
  uint8_t imu_ok;
  uint8_t mag_ok;
  uint8_t quat_enabled;
  uint8_t dio_level;
  uint8_t rec_state;
  uint8_t schedule_armed;
  uint8_t schedule_error;
  uint8_t reserved_status;
  uint16_t sample_hz;
  uint16_t dio_edges;
  uint32_t seq;
  uint64_t generated_samples;
  uint64_t saved_samples;
  uint64_t sd_errors;
  int64_t clock_offset_us;
  int64_t start_at_time_us;
  int64_t stop_at_time_us;
  int16_t ax;
  int16_t ay;
  int16_t az;
  int16_t gx;
  int16_t gy;
  int16_t gz;
  int16_t mx;
  int16_t my;
  int16_t mz;
  int16_t qw;
  int16_t qx;
  int16_t qy;
  int16_t qz;
};
#pragma pack(pop)

static uint32_t g_last_identity_status_ms = 0;
static IdentityPacket g_master_identity = {};
static bool g_master_identity_verified = false;
static volatile bool g_identify_request_pending = false;
static IdentifyRequestPacket g_identify_pending_request = {};
static volatile bool g_identify_pending_from_espnow = false;
static volatile bool g_identify_ack_pending = false;
static IdentifyAckPacket g_identify_pending_ack = {};
static bool g_identify_active = false;
static char g_identify_active_command_id[IDENTIFY_COMMAND_ID_MAX + 1] = {};
static uint8_t g_identify_active_target[6] = {};
static uint32_t g_identify_deadline_ms = 0;
static uint32_t g_identify_last_toggle_ms = 0;
static int g_identify_prior_led_level = HIGH;
static int g_identify_led_level = HIGH;
static IdentifyAckPacket g_identify_last_ack = {};
static bool g_identify_last_ack_valid = false;

static void efuseBaseMac(uint8_t out[6]) {
  const uint64_t raw = ESP.getEfuseMac();
  for (int i = 0; i < 6; i++) {
    out[5 - i] = (uint8_t)(raw >> (i * 8));
  }
}

static void formatCanonicalDeviceId(const uint8_t mac[6], char *out, size_t out_len) {
  snprintf(out, out_len, "esp32:%02x%02x%02x%02x%02x%02x",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

static void formatDisplayMac(const uint8_t mac[6], char *out, size_t out_len) {
  snprintf(out, out_len, "%02X:%02X:%02X:%02X:%02X:%02X",
           mac[0], mac[1], mac[2], mac[3], mac[4], mac[5]);
}

static void readLocalIdentity(IdentityPacket *identity) {
  memset(identity, 0, sizeof(*identity));
  identity->magic = IDENTITY_PACKET_MAGIC;
  identity->type = IDENTITY_PACKET_TYPE;
  identity->version = IDENTITY_PACKET_VERSION;
  identity->packet_size = sizeof(IdentityPacket);
  efuseBaseMac(identity->base_mac);
#if ENABLE_ESPNOW
  esp_read_mac(identity->sta_mac, ESP_MAC_WIFI_STA);
  esp_read_mac(identity->ap_mac, ESP_MAC_WIFI_SOFTAP);
#endif
  memcpy(identity->espnow_mac,
         wifi_soft_ap ? identity->ap_mac : identity->sta_mac, 6);
  identity->role = NODE_IS_MASTER ? IDENTITY_ROLE_MASTER : IDENTITY_ROLE_SLAVE;
  identity->capabilities =
      STEPESP_IDENTIFY_LED_VERIFIED ? IDENTITY_CAP_IDENTIFY : 0u;
  identity->verified = 1;
}

static bool sdRecordStart(const char *, const char *requested_session = nullptr);
static void sdRecordStop();
static uint32_t g_last_slave_status_ms = 0;

static uint8_t slaveRecStateCode() {
  if (strcmp(g_rec_state, "armed") == 0) return SLAVE_REC_STATE_ARMED;
  if (strcmp(g_rec_state, "recording") == 0) return SLAVE_REC_STATE_RECORDING;
  if (strcmp(g_rec_state, "finalizing") == 0) return SLAVE_REC_STATE_FINALIZING;
  if (strcmp(g_rec_state, "finalized") == 0) return SLAVE_REC_STATE_FINALIZED;
  if (strcmp(g_rec_state, "failed") == 0) return SLAVE_REC_STATE_ERROR;
  return SLAVE_REC_STATE_IDLE;
}

static uint8_t slaveScheduleErrorCode() {
  if (strcmp(g_last_schedule_error, "unsynced_start") == 0) return SLAVE_SCHEDULE_ERROR_UNSYNCED_START;
  if (strcmp(g_last_schedule_error, "late_start") == 0) return SLAVE_SCHEDULE_ERROR_LATE_START;
  if (strcmp(g_last_schedule_error, "sd_start_failed") == 0) return SLAVE_SCHEDULE_ERROR_SD_START_FAILED;
  return SLAVE_SCHEDULE_ERROR_NONE;
}

#if ENABLE_ESPNOW
static void maybeRegisterMasterPeer(const esp_now_recv_info_t *info) {
#if ESPNOW_UNICAST
  if (g_master_peer_registered || !info || !info->src_addr) return;
  memcpy(g_master_mac, info->src_addr, 6);
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, g_master_mac, 6);
  peer.channel = ESPNOW_WIFI_CHANNEL;
  peer.ifidx = wifi_soft_ap ? WIFI_IF_AP : WIFI_IF_STA;
  peer.encrypt = false;
  if (esp_now_add_peer(&peer) == ESP_OK) {
    g_master_peer_registered = true;
    Serial.printf("[ESPNOW] registered master peer %02X:%02X:%02X:%02X:%02X:%02X\n",
                  g_master_mac[0], g_master_mac[1], g_master_mac[2],
                  g_master_mac[3], g_master_mac[4], g_master_mac[5]);
  }
#else
  (void)info;
#endif
}

void onEspNowRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (NODE_IS_MASTER) return;
  if (len == (int)sizeof(IdentifyRequestPacket) &&
      data[0] == IDENTIFY_PACKET_MAGIC) {
    const IdentifyRequestPacket *request =
        (const IdentifyRequestPacket *)data;
    uint8_t self_base_mac[6] = {};
    efuseBaseMac(self_base_mac);
    const bool command_terminated =
        memchr(request->command_id, '\0',
               sizeof(request->command_id)) != nullptr;
    if (request->type == IDENTIFY_REQUEST_TYPE &&
        request->version == IDENTIFY_PACKET_VERSION &&
        request->packet_size == sizeof(IdentifyRequestPacket) &&
        command_terminated && request->command_id[0] != '\0' &&
        request->requested_duration_ms >= IDENTIFY_DURATION_MIN_MS &&
        request->requested_duration_ms <= IDENTIFY_DURATION_MAX_MS &&
        memcmp(request->target_mac, self_base_mac, 6) == 0 &&
        !g_identify_request_pending) {
      maybeRegisterMasterPeer(info);
      g_identify_pending_request = *request;
      g_identify_pending_from_espnow = true;
      g_identify_request_pending = true;
      g_espnow_last_rx_ms = millis();
    }
    return;
  }
  if (len == (int)sizeof(IdentityPacket) &&
      data[0] == IDENTITY_PACKET_MAGIC) {
    const IdentityPacket *identity = (const IdentityPacket *)data;
    if (identity->type == IDENTITY_PACKET_TYPE &&
        identity->version == IDENTITY_PACKET_VERSION &&
        identity->packet_size == sizeof(IdentityPacket) &&
        identity->role == IDENTITY_ROLE_MASTER &&
        identity->verified == 1) {
      maybeRegisterMasterPeer(info);
      g_master_identity = *identity;
      g_master_identity_verified = true;
      g_espnow_last_rx_ms = millis();
    }
    return;
  }
  // FREQ relay: compact 4-byte packet (magic, cmd, sample_hz LE).
  if (len == (int)sizeof(FreqCmdPacket) && data[0] == CMD_MAGIC && data[1] == CMD_SET_FREQ) {
    maybeRegisterMasterPeer(info);
    g_espnow_last_rx_ms = millis();
    const FreqCmdPacket *freq = (const FreqCmdPacket *)data;
    applySampleRateHz((int)freq->sample_hz);
#if !SERIAL_OUTPUT_BINARY
    Serial.printf("ESP-NOW SET_FREQ -> %u Hz\n", (unsigned)freq->sample_hz);
#endif
    return;
  }
  // Configuration relay: ACC/GYR range presets selected in the plugin.
  if (len == (int)sizeof(CfgCmdPacket) && data[0] == CMD_MAGIC && data[1] == CMD_SET_CFG) {
    maybeRegisterMasterPeer(info);
    g_espnow_last_rx_ms = millis();
    const CfgCmdPacket *cfg = (const CfgCmdPacket *)data;
    const uint8_t preset = (uint8_t)constrain((int)cfg->preset, 0, 3);
    if (cfg->kind == 1) {
      g_acc_preset = preset;
      icmApplyRangePresets();
#if !SERIAL_OUTPUT_BINARY
      Serial.printf("ESP-NOW SET_CFG ACC -> %u\n", (unsigned)preset);
#endif
    } else if (cfg->kind == 2) {
      g_gyr_preset = preset;
      icmApplyRangePresets();
#if !SERIAL_OUTPUT_BINARY
      Serial.printf("ESP-NOW SET_CFG GYR -> %u\n", (unsigned)preset);
#endif
    }
    return;
  }
  // Command relay from master. Old packets are 2 bytes; newer REC_START
  // packets include the master's requested wall-clock session id.
  if ((len == 2 || len == (int)sizeof(CmdPacket)) && data[0] == CMD_MAGIC) {
    maybeRegisterMasterPeer(info);
    g_espnow_last_rx_ms = millis();
    const CmdPacket *cmd = len == (int)sizeof(CmdPacket) ? (const CmdPacket *)data : nullptr;
    const uint8_t command = cmd ? cmd->cmd : data[1];
    switch (command) {
      case CMD_START_STREAM:
#if ENABLE_TCP
        // The direct slave TCP host owns START in Wi-Fi mode. Starting here
        // can emit binary data before that host receives STARTED/SENSORS.
#else
        streaming = true;
#endif
        break;
      case CMD_STOP_STREAM:  streaming = false; break;
      case CMD_FILTER_ON:
        g_filter_on = true;
        vqfReinitFilter();
        g_loop_overruns = 0;
        g_max_loop_us = 0;
        profReset();
#if !SERIAL_OUTPUT_BINARY
        Serial.println("ESP-NOW FILTER ON");
#endif
        break;
      case CMD_FILTER_OFF:
        g_filter_on = false;
        g_loop_overruns = 0;
        g_max_loop_us = 0;
        profReset();
#if !SERIAL_OUTPUT_BINARY
        Serial.println("ESP-NOW FILTER OFF");
#endif
        break;
      case CMD_REC_START:
        if (cmd && cmd->session_id[0]) {
          strncpy(g_espnow_requested_session, cmd->session_id, sizeof(g_espnow_requested_session) - 1);
          g_espnow_requested_session[sizeof(g_espnow_requested_session) - 1] = '\0';
        } else {
          g_espnow_requested_session[0] = '\0';
        }
        g_espnow_requested_start_at_us = (cmd && (cmd->flags & CMD_FLAG_SCHEDULED))
                                             ? cmd->start_at_time_us
                                             : 0;
        g_espnow_requested_stop_at_us = (cmd && (cmd->flags & CMD_FLAG_SCHEDULED))
                                            ? cmd->stop_at_time_us
                                            : 0;
        g_espnow_rec_start_pending = true;
        break;
      case CMD_REC_STOP:
        g_espnow_requested_stop_at_us = (cmd && (cmd->flags & CMD_FLAG_SCHEDULED))
                                            ? cmd->stop_at_time_us
                                            : 0;
        g_espnow_rec_stop_pending  = true;
        break;
    }
    return;
  }
  // Clock sync packet (12 bytes)
  if (len < (int)sizeof(SyncPacket)) return;
  maybeRegisterMasterPeer(info);
  const SyncPacket *pkt = (const SyncPacket *)data;
  int64_t recv_us = (int64_t)esp_timer_get_time();
  g_clock_offset_us      = (int64_t)pkt->time_us - recv_us;
  g_espnow_sync_received = true;
  g_espnow_last_seq      = pkt->seq;
  g_espnow_last_rx_ms    = millis();
}
void onEspNowSent(const wifi_tx_info_t *tx_info, esp_now_send_status_t status) {
  (void)tx_info; (void)status;
}
#endif

static int64_t recNowUs() {
  int64_t t_us = (int64_t)esp_timer_get_time();
#if ENABLE_ESPNOW
  if (!NODE_IS_MASTER && g_espnow_sync_received) t_us += g_clock_offset_us;
#endif
  return t_us;
}

static void recSetScheduleError(const char *err) {
  strncpy(g_last_schedule_error, err, sizeof(g_last_schedule_error) - 1);
  g_last_schedule_error[sizeof(g_last_schedule_error) - 1] = '\0';
  strncpy(g_last_rec_error, err, sizeof(g_last_rec_error) - 1);
  g_last_rec_error[sizeof(g_last_rec_error) - 1] = '\0';
}

static bool recLogGateOpen() {
  if (!g_sd_recording) return false;
  if (!g_rec_schedule_enabled) return true;
  const int64_t now_us = recNowUs();
  if (g_rec_stop_at_us > 0 && now_us >= g_rec_stop_at_us) return false;
  if (g_rec_start_at_us > 0 && now_us < g_rec_start_at_us) return false;
  if (g_rec_armed) {
    g_rec_armed = false;
    strncpy(g_rec_state, "recording", sizeof(g_rec_state) - 1);
  }
  return true;
}

static void recMaybeScheduledStop() {
#if ENABLE_SD
  if (g_sd_recording && g_rec_schedule_enabled && g_rec_stop_at_us > 0 &&
      recNowUs() >= g_rec_stop_at_us) {
    sdRecordStop();
  }
#endif
}

static void icmSpiBegin() {
  pinMode(PIN_ICM_CS, OUTPUT);
  digitalWrite(PIN_ICM_CS, HIGH);
  ICM_SPI.begin(PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, PIN_ICM_CS);
}

static bool spiBusTake(TickType_t timeout) {
  if (!g_spi_mutex) return true;
  if (xSemaphoreTake(g_spi_mutex, timeout) == pdTRUE) return true;
  g_spi_mutex_timeouts++;
  return false;
}

static void spiBusGive() {
  if (g_spi_mutex) xSemaphoreGive(g_spi_mutex);
}

static bool icmWriteAddr(uint8_t addr, uint8_t reg, uint8_t val) {
  (void)addr;
  if (!spiBusTake(0)) return false;
  ICM_SPI.beginTransaction(SPISettings(kIcmSpiHz, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_ICM_CS, LOW);
  ICM_SPI.transfer(reg & 0x7F);
  ICM_SPI.transfer(val);
  digitalWrite(PIN_ICM_CS, HIGH);
  ICM_SPI.endTransaction();
  spiBusGive();
  return true;
}

static bool icmReadAddr(uint8_t addr, uint8_t reg, uint8_t *val) {
  (void)addr;
  if (!spiBusTake(0)) return false;
  ICM_SPI.beginTransaction(SPISettings(kIcmSpiHz, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_ICM_CS, LOW);
  ICM_SPI.transfer(reg | 0x80);
  *val = ICM_SPI.transfer(0x00);
  digitalWrite(PIN_ICM_CS, HIGH);
  ICM_SPI.endTransaction();
  spiBusGive();
  return true;
}

static bool icmReadBytes(uint8_t reg, uint8_t *buf, size_t len) {
  if (!spiBusTake(0)) return false;
  ICM_SPI.beginTransaction(SPISettings(kIcmSpiHz, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_ICM_CS, LOW);
  ICM_SPI.transfer(reg | 0x80);
  for (size_t i = 0; i < len; i++) {
    buf[i] = ICM_SPI.transfer(0x00);
  }
  digitalWrite(PIN_ICM_CS, HIGH);
  ICM_SPI.endTransaction();
  spiBusGive();
  return true;
}

static void icmSelectBank(uint8_t addr, uint8_t bank) {
  icmWriteAddr(addr, ICM_REG_BANK_SEL, (uint8_t)((bank & 0x03) << 4));
}

static bool icmReadWhoAmI(uint8_t addr, uint8_t *who) {
  icmSelectBank(addr, 0);
  return icmReadAddr(addr, ICM_WHO_AM_I, who);
}

static bool icmWrite(uint8_t reg, uint8_t val) {
  return icmWriteAddr(0, reg, val);
}

static bool icmReadReg(uint8_t reg, uint8_t *val) {
  return icmReadAddr(0, reg, val);
}
static void printBootDiagnostics() {
#if BOOT_DIAGNOSTICS
  Serial.println();
  Serial.println("========================================");
  Serial.println("  STEP ESP32-S3 NODE — BOOT DIAGNOSTICS");
  Serial.println("========================================");
  Serial.printf("Firmware: %s\n", FIRMWARE_VERSION);
  Serial.printf("Board target: XIAO_ESP32S3 (Sense)\n");
  Serial.printf("ICM HSPI SCK: GPIO%d (D3)  MISO: GPIO%d (D5)  MOSI: GPIO%d (D1)  CS: GPIO%d (D4)\n",
                PIN_SPI_SCK, PIN_SPI_MISO, PIN_SPI_MOSI, PIN_ICM_CS);
  Serial.printf("ICM ODR: gyro_div=%u accel_div=%u odr_align=1 dlpf=%s dlpf_cfg=%u\n",
                kIcmGyroSmplrtDiv, kIcmAccelSmplrtDiv,
                kIcmDlpfEnabled ? "on" : "off", kIcmDlpfCfg);
  Serial.printf("Mag poll: %.0f Hz, cached between polls\n", kMagRateHz);
  Serial.printf("Sample rate: %d Hz  channels: %d\n", g_sample_hz, NUM_CHANNELS);

  Serial.println("--- ICM20948 SPI WHO_AM_I (expect 0xEA) ---");
  icmSpiBegin();
  delay(50);
  uint8_t spi_who = 0;
  icmReadWhoAmI(0, &spi_who);
  Serial.printf("  CS GPIO%d -> WHO_AM_I 0x%02X %s\n", PIN_ICM_CS, spi_who,
                spi_who == ICM20948_WHOAMI_VAL ? "OK" : "unexpected");
  Serial.println("========================================");
#endif
}

static void initDio() {
  pinMode(PIN_DIO, INPUT_PULLUP);
  bool level = digitalRead(PIN_DIO);
  dio_state.stable_high = level;
  dio_state.pending_raw = level;
  dio_state.pending_since_ms = millis();
  Serial.printf("DIO: GPIO%d (pad D0) pull-up — initial level=%d (1=idle, 0=GND)\n",
                PIN_DIO, level ? 1 : 0);
  Serial.println("DIO: input active for sync/commands; included as channel 13 in 14-channel OE stream");
}

static void updateDio() {
  bool raw = digitalRead(PIN_DIO);
  uint32_t now = millis();
  if (raw != dio_state.pending_raw) {
    dio_state.pending_raw = raw;
    dio_state.pending_since_ms = now;
  }
  if ((now - dio_state.pending_since_ms) >= (uint32_t)DIO_DEBOUNCE_MS &&
      dio_state.pending_raw != dio_state.stable_high) {
    dio_state.stable_high = dio_state.pending_raw;
    if (dio_state.edge_count < 0x7FFF) {
      dio_state.edge_count++;
    }
  }
}

static int16_t packDioCh6() {
  uint16_t packed = (dio_state.stable_high ? 1u : 0u) |
                    ((uint32_t)(dio_state.edge_count & 0x7FFFu) << 1);
  return (int16_t)packed;
}

static void icmAuxWriteByte(uint8_t slave_addr, uint8_t reg, uint8_t val) {
  icmSelectBank(0, 3);
  icmWrite(ICM_I2C_SLV0_ADDR, slave_addr);
  icmWrite(ICM_I2C_SLV0_REG, reg);
  icmWrite(ICM_I2C_SLV0_DO, val);
  icmWrite(ICM_I2C_SLV0_CTRL, 0x81);
  delay(10);
  icmWrite(ICM_I2C_SLV0_CTRL, 0x00);
  icmSelectBank(0, 0);
}

static uint8_t icmAuxReadByte(uint8_t slave_addr, uint8_t reg) {
  icmSelectBank(0, 3);
  icmWrite(ICM_I2C_SLV0_ADDR, (uint8_t)(0x80 | slave_addr));
  icmWrite(ICM_I2C_SLV0_REG, reg);
  icmWrite(ICM_I2C_SLV0_CTRL, 0x81);
  delay(10);
  icmSelectBank(0, 0);
  uint8_t val = 0;
  icmReadReg(ICM_EXT_SENS_DATA_00, &val);
  icmSelectBank(0, 3);
  icmWrite(ICM_I2C_SLV0_CTRL, 0x00);
  icmSelectBank(0, 0);
  return val;
}

static bool initIcm20948() {
  icmSpiBegin();
  uint8_t who = 0;
  if (!icmReadWhoAmI(0, &who) || who != ICM20948_WHOAMI_VAL) {
    Serial.printf("ICM20948: synthetic fallback - SPI WHO_AM_I=0x%02X (expected 0xEA)\n", who);
    return false;
  }

  icmSelectBank(0, 0);
  icmWrite(ICM_PWR_MGMT_1, 0x01);
  delay(100);
  icmConfigureOutputRate();
  Serial.printf("ICM20948: OK on SPI CS GPIO%d WHO_AM_I=0xEA\n", PIN_ICM_CS);
  Serial.printf("ICM20948: ODR gyro_div=%u accel_div=%u odr_align=1 dlpf=%s cfg=%u\n",
                kIcmGyroSmplrtDiv, kIcmAccelSmplrtDiv,
                kIcmDlpfEnabled ? "on" : "off", kIcmDlpfCfg);
  icmApplyRangePresets();
  return true;
}

static bool readImuRaw(int16_t out[6]) {
  uint8_t raw[12];
  icmSelectBank(0, 0);
  if (!icmReadBytes(ICM_ACCEL_XOUT_H, raw, sizeof(raw))) return false;

  auto read16be = [](const uint8_t *p) {
    return (int16_t)(((uint16_t)p[0] << 8) | p[1]);
  };
  out[0] = read16be(&raw[0]);
  out[1] = read16be(&raw[2]);
  out[2] = read16be(&raw[4]);
  out[3] = read16be(&raw[6]);
  out[4] = read16be(&raw[8]);
  out[5] = read16be(&raw[10]);
  return true;
}

static bool initAk09916() {
  if (!icm_ok) return false;

  icmSelectBank(0, 0);
  icmWrite(ICM_USER_CTRL, 0x20);
  delay(10);
  icmSelectBank(0, 3);
  icmWrite(ICM_I2C_MST_CTRL, 0x07);
  delay(10);
  icmSelectBank(0, 0);

  uint8_t who = icmAuxReadByte(AK09916_ADDR, AK09916_WIA2);
  if (who != AK09916_WIA2_VAL) {
    Serial.printf("AK09916: unavailable through ICM SPI aux bus WIA2=0x%02X\n", who);
    return false;
  }

  icmAuxWriteByte(AK09916_ADDR, AK09916_CNTL3, 0x01);
  delay(10);
  icmAuxWriteByte(AK09916_ADDR, AK09916_CNTL2, AK09916_MODE_CONT_100HZ);

  icmSelectBank(0, 3);
  icmWrite(ICM_I2C_SLV0_ADDR, (uint8_t)(0x80 | AK09916_ADDR));
  icmWrite(ICM_I2C_SLV0_REG, AK09916_ST1);
  // Read ST1, XYZ, TMPS, and ST2. Reading ST2 completes the AK09916 sample.
  icmWrite(ICM_I2C_SLV0_CTRL, 0x89);
  delay(10);
  icmSelectBank(0, 0);

  Serial.println("AK09916: OK through ICM SPI aux bus, continuous 100 Hz, cached between polls");
  return true;
}

static bool readMagRaw(int16_t out[3], bool *fresh) {
  if (fresh != nullptr) *fresh = false;
  if (!mag_ok) return false;

  uint8_t mag_raw[9];
  icmSelectBank(0, 0);
  if (!icmReadBytes(ICM_EXT_SENS_DATA_00, mag_raw, sizeof(mag_raw))) return false;

  if ((mag_raw[0] & 0x01) == 0) {
    if (g_have_mag) {
      out[0] = g_last_mag[0];
      out[1] = g_last_mag[1];
      out[2] = g_last_mag[2];
      return true;
    }
    return false;
  }

  uint8_t st2 = mag_raw[8];
  if ((st2 & 0x08) != 0) {
    if (g_have_mag) {
      out[0] = g_last_mag[0];
      out[1] = g_last_mag[1];
      out[2] = g_last_mag[2];
      return true;
    }
    return false;
  }

  g_last_mag[0] = out[0] = (int16_t)((uint16_t)mag_raw[1] | ((uint16_t)mag_raw[2] << 8));
  g_last_mag[1] = out[1] = (int16_t)((uint16_t)mag_raw[3] | ((uint16_t)mag_raw[4] << 8));
  g_last_mag[2] = out[2] = (int16_t)((uint16_t)mag_raw[5] | ((uint16_t)mag_raw[6] << 8));
  g_have_mag = true;
  if (fresh != nullptr) *fresh = true;
  return true;
}

static void readImu(int16_t out[6]) {
  if (icm_ok && readImuRaw(out)) return;

  float t = millis() * 0.01f;
  out[0] = (int16_t)(1000 * sinf(t));
  out[1] = (int16_t)(500 * cosf(t));
  out[2] = 16384;
  out[3] = out[4] = out[5] = 0;
}

static void readMag(int16_t out[3], bool *fresh) {
  if (fresh != nullptr) *fresh = false;

  const uint32_t now_us = micros();
  const bool poll_due = !g_have_mag || g_last_mag_poll_us == 0 ||
                        (uint32_t)(now_us - g_last_mag_poll_us) >= kMagPollPeriodUs;
  if (poll_due) {
    g_last_mag_poll_us = now_us;
    if (readMagRaw(out, fresh)) return;
  }

  out[0] = g_last_mag[0];
  out[1] = g_last_mag[1];
  out[2] = g_last_mag[2];
}

// Open Ephys header offset field (int32 LE): low 32 bits of esp_timer_get_time() µs since boot.
// offset==0 = legacy frames (host/Plugin use arrival-time pacing). Same clock on every slave;
// cross-board alignment needs START pulse or host merge — see docs/open-ephys-plugin.md.
static void fillOeHeader(OeHeader *hdr) {
  int64_t t_us = (int64_t)esp_timer_get_time();
#if ENABLE_ESPNOW
  if (!NODE_IS_MASTER && g_espnow_sync_received) t_us += g_clock_offset_us;
#endif
  hdr->offset = (int32_t)(uint32_t)t_us;
  hdr->num_channels = NUM_CHANNELS;
  hdr->samples_per_channel = 1;
  hdr->element_size = 2;
  hdr->bit_depth = 3;  // Open Ephys Ephys Socket: OpenCV S16 enum
  hdr->num_bytes = NUM_CHANNELS * 1 * 2;
}

#if ENABLE_ESPNOW
static void sendEspNowSync() {
  if (!NODE_IS_MASTER || !wifi_up) return;
  SyncPacket pkt = {seq, (int64_t)esp_timer_get_time()};
  uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_send(bcast, (uint8_t *)&pkt, sizeof(pkt));
}
#else
static void sendEspNowSync() {}
#endif

static void sendSlaveStatus() {
#if ENABLE_ESPNOW
  if (NODE_IS_MASTER || !wifi_up) return;
  const uint32_t now_ms = millis();
  if ((uint32_t)(now_ms - g_last_slave_status_ms) < SLAVE_STATUS_INTERVAL_MS) return;
  g_last_slave_status_ms = now_ms;

  SlaveStatusPacket pkt = {};
  pkt.magic = SLAVE_STATUS_MAGIC;
  pkt.version = SLAVE_STATUS_VERSION;
  pkt.packet_size = sizeof(SlaveStatusPacket);
  const uint64_t mac = ESP.getEfuseMac();
  pkt.slave_id = (uint32_t)(mac & 0xFFFFFFFFULL);
  pkt.sd_ready = g_sd_ready ? 1 : 0;
  pkt.sd_recording = g_sd_recording ? 1 : 0;
  pkt.streaming = streaming ? 1 : 0;
  pkt.sync_received = g_espnow_sync_received ? 1 : 0;
  pkt.imu_ok = icm_ok ? 1 : 0;
  pkt.mag_ok = (mag_ok && g_have_mag) ? 1 : 0;
  pkt.quat_enabled = g_filter_on ? 1 : 0;
  pkt.dio_level = dio_state.stable_high ? 1 : 0;
  pkt.rec_state = slaveRecStateCode();
  pkt.schedule_armed = g_rec_armed ? 1 : 0;
  pkt.schedule_error = slaveScheduleErrorCode();
  pkt.reserved_status = 0;
  pkt.sample_hz = g_sample_hz;
  pkt.dio_edges = dio_state.edge_count;
  pkt.seq = seq;
  pkt.generated_samples = g_generated_samples;
  pkt.saved_samples = g_sd_saved_samples;
  pkt.sd_errors = sdErrorTotal();
  pkt.clock_offset_us = g_clock_offset_us;
  pkt.start_at_time_us = g_rec_start_at_us;
  pkt.stop_at_time_us = g_rec_stop_at_us;
  pkt.ax = channels[0];
  pkt.ay = channels[1];
  pkt.az = channels[2];
  pkt.gx = channels[3];
  pkt.gy = channels[4];
  pkt.gz = channels[5];
  pkt.mx = channels[6];
  pkt.my = channels[7];
  pkt.mz = channels[8];
  pkt.qw = channels[9];
  pkt.qx = channels[10];
  pkt.qy = channels[11];
  pkt.qz = channels[12];

#if ESPNOW_UNICAST
  if (g_master_peer_registered) {
    esp_now_send(g_master_mac, (uint8_t *)&pkt, sizeof(pkt));
  } else {
    uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    esp_now_send(bcast, (uint8_t *)&pkt, sizeof(pkt));
  }
#else
  uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_send(bcast, (uint8_t *)&pkt, sizeof(pkt));
#endif
#endif
}

static void sendIdentityPacket() {
#if ENABLE_ESPNOW
  if (NODE_IS_MASTER || !wifi_up) return;
  const uint32_t now_ms = millis();
  if ((uint32_t)(now_ms - g_last_identity_status_ms) <
      IDENTITY_STATUS_INTERVAL_MS) {
    return;
  }
  g_last_identity_status_ms = now_ms;
  IdentityPacket identity = {};
  readLocalIdentity(&identity);
#if ESPNOW_UNICAST
  if (g_master_peer_registered) {
    esp_now_send(g_master_mac, (uint8_t *)&identity, sizeof(identity));
  } else {
    uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
    esp_now_send(bcast, (uint8_t *)&identity, sizeof(identity));
  }
#else
  uint8_t bcast[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
  esp_now_send(bcast, (uint8_t *)&identity, sizeof(identity));
#endif
#endif
}

static void resetStreamStats() {
  g_stream_offered = 0;
  g_stream_enqueued = 0;
  g_stream_sent = 0;
  g_stream_queue_drops = 0;
  g_stream_send_errors = 0;
  g_stream_queue_max_depth = 0;
  g_max_stream_send_us = 0;
  if (g_stream_queue) xQueueReset(g_stream_queue);
}

static void queueStreamRecord() {
  if (!streaming || !g_stream_queue || g_transfer_active) return;

  StreamRecord rec = {};
  fillOeHeader(&rec.header);
  memcpy(rec.ch, channels, sizeof(rec.ch));
  rec.seq = seq;
  g_stream_offered++;

  if (xQueueSend(g_stream_queue, &rec, 0) != pdTRUE) {
    StreamRecord stale;
    if (xQueueReceive(g_stream_queue, &stale, 0) == pdTRUE) {
      g_stream_queue_drops++;
    }
    if (xQueueSend(g_stream_queue, &rec, 0) != pdTRUE) {
      g_stream_queue_drops++;
      return;
    }
  }

  g_stream_enqueued++;
  uint32_t depth = uxQueueMessagesWaiting(g_stream_queue);
  if (depth > g_stream_queue_max_depth) g_stream_queue_max_depth = depth;
}

static void streamWriteTask(void *) {
  Serial.printf("Stream writer: core=%d priority=%u queue=%u transport=%s\n",
                xPortGetCoreID(), (unsigned)uxTaskPriorityGet(NULL),
                (unsigned)STREAM_QUEUE_DEPTH,
#if ENABLE_TCP
                WIFI_STREAM_OVER_TCP ? "tcp" : "udp:55001"
#else
                "usb-serial"
#endif
  );

  StreamRecord rec;
  while (true) {
    if (!g_stream_queue ||
        xQueueReceive(g_stream_queue, &rec, pdMS_TO_TICKS(100)) != pdTRUE) {
      continue;
    }
    if (!streaming || g_transfer_active) continue;

    uint32_t t0 = micros();
    bool sent = false;
#if ENABLE_TCP
#if WIFI_STREAM_OVER_TCP
    if (wifi_up && client.fd() >= 0) {
      static constexpr size_t kWireFrameBytes =
          sizeof(OeHeader) + NUM_CHANNELS * sizeof(int16_t);
      uint8_t wire_frame[kWireFrameBytes];
      memcpy(wire_frame, &rec.header, sizeof(rec.header));
      memcpy(wire_frame + sizeof(rec.header), rec.ch, sizeof(rec.ch));
      sent = tcpWriteBytes(wire_frame, sizeof(wire_frame), TCP_WRITE_TIMEOUT_MS);
      if (sent) {
        g_tcp_consecutive_write_failures = 0;
      } else if (++g_tcp_consecutive_write_failures >= TCP_WRITE_FAILURE_LIMIT) {
        g_tcp_reset_requested = true;
      }
    }
#else
    const uint32_t target_raw = g_stream_target_ip;
    if (wifi_up && target_raw != 0) {
      IPAddress target(target_raw);
      const int began = stream_udp.beginPacket(target, UDP_STREAM_PORT);
      size_t written = 0;
      if (began == 1) {
        written += stream_udp.write((const uint8_t *)&rec.header, sizeof(rec.header));
        written += stream_udp.write((const uint8_t *)rec.ch, sizeof(rec.ch));
        const int ended = stream_udp.endPacket();
        sent = written == sizeof(rec.header) + sizeof(rec.ch) && ended == 1;
      }
    }
#endif
#elif ENABLE_SERIAL_BENCH
    if (!csv_banner_sent) {
      Serial.printf("# STEP boot complete icm=%s spi_cs=%d mag=%s channels=ax,ay,az,gx,gy,gz,mx,my,mz,qw,qx,qy,qz,dio\n",
                    icm_ok ? "OK" : "FALLBACK", PIN_ICM_CS,
                    mag_ok ? "OK" : "FALLBACK");
      csv_banner_sent = true;
    }
#if SERIAL_OUTPUT_BINARY
    const size_t header_written =
        Serial.write((const uint8_t *)&rec.header, sizeof(rec.header));
    const size_t payload_written =
        Serial.write((const uint8_t *)rec.ch, sizeof(rec.ch));
    sent = header_written == sizeof(rec.header) &&
           payload_written == sizeof(rec.ch);
#else
    sent = Serial.printf("%lu,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d\n",
                         (unsigned long)rec.seq,
                         rec.ch[0], rec.ch[1], rec.ch[2], rec.ch[3], rec.ch[4],
                         rec.ch[5], rec.ch[6], rec.ch[7], rec.ch[8], rec.ch[9],
                         rec.ch[10], rec.ch[11], rec.ch[12], rec.ch[13]) > 0;
#endif
#endif
    const uint32_t elapsed = (uint32_t)(micros() - t0);
    if (elapsed > g_max_stream_send_us) g_max_stream_send_us = elapsed;
    if (sent) {
      g_stream_sent++;
    } else {
      g_stream_send_errors++;
    }
  }
}
static void sdRecordStop();
static void recReplyToHost(const char *text);

static void controlPrintf(const char *fmt, ...) {
  char buf[256];
  va_list args;
  va_start(args, fmt);
  vsnprintf(buf, sizeof(buf), fmt, args);
  va_end(args);
  recReplyToHost(buf);
}

static uint32_t recCrc32Update(uint32_t crc, const uint8_t *data, size_t len) {
  crc = ~crc;
  for (size_t i = 0; i < len; i++) {
    crc ^= data[i];
    for (int bit = 0; bit < 8; bit++) {
      uint32_t mask = -(crc & 1u);
      crc = (crc >> 1) ^ (0xEDB88320UL & mask);
    }
  }
  return ~crc;
}

static uint32_t checksumSdFile(const char *path, uint64_t *size_out) {
#if ENABLE_SD
  uint8_t buf[128];
  uint32_t crc = 0;
  uint64_t total = 0;
  File f = SD.open(path, FILE_READ);
  if (!f) {
    if (size_out) *size_out = 0;
    return 0;
  }
  while (f.available()) {
    size_t n = f.read(buf, sizeof(buf));
    if (n == 0) break;
    crc = recCrc32Update(crc, buf, n);
    total += n;
  }
  f.close();
  if (size_out) *size_out = total;
  return crc;
#else
  if (size_out) *size_out = 0;
  return 0;
#endif
}

static void makeSessionId(const char *requested_session = nullptr) {
  if (requested_session && requested_session[0]) {
    strncpy(g_rec_session_id, requested_session, sizeof(g_rec_session_id) - 1);
    g_rec_session_id[sizeof(g_rec_session_id) - 1] = '\0';
    return;
  }
  snprintf(g_rec_session_id, sizeof(g_rec_session_id), "%08lx%08lx",
           (unsigned long)millis(), (unsigned long)seq);
}

static uint32_t recGraceRemainingMs() {
  if (strcmp(g_rec_state, "host-disconnected-grace") != 0 || g_rec_grace_deadline_ms == 0)
    return 0;
  uint32_t now = millis();
  return (int32_t)(g_rec_grace_deadline_ms - now) > 0 ? g_rec_grace_deadline_ms - now : 0;
}

static void recMarkControlConnected() {
  if (strcmp(g_rec_state, "host-disconnected-grace") == 0) {
    strncpy(g_rec_state, "recording", sizeof(g_rec_state) - 1);
    g_rec_grace_deadline_ms = 0;
  }
}

static void recMarkControlDisconnected() {
  if (g_sd_recording && strcmp(g_rec_state, "recording") == 0) {
    strncpy(g_rec_state, "host-disconnected-grace", sizeof(g_rec_state) - 1);
    g_rec_grace_deadline_ms = millis() + REC_RECONNECT_GRACE_MS;
  }
}

static void recMaybeFinalizeTimeout() {
  if (strcmp(g_rec_state, "host-disconnected-grace") == 0 && recGraceRemainingMs() == 0) {
    strncpy(g_finalization_reason, "disconnect_timeout", sizeof(g_finalization_reason) - 1);
    sdRecordStop();
  }
}

static bool recWriteBytes(const uint8_t *data, size_t len) {
#if ENABLE_TCP && !ENABLE_SERIAL_BENCH
  const bool sent = tcpWriteBytes(data, len, 5000UL);
  if (!sent)
    Serial.printf("REC transfer short write: %u bytes\n", (unsigned)len);
  return sent;
#else
  return Serial.write(data, len) == len;
#endif
}

static void writeSdrfFrame(const char *session_id, uint8_t type, uint32_t chunk_index,
                           uint64_t offset, const uint8_t *payload, uint32_t payload_len,
                           uint64_t total_size, uint32_t flags) {
  SdrfHeader hdr = {};
  hdr.magic[0] = 'S'; hdr.magic[1] = 'D'; hdr.magic[2] = 'R'; hdr.magic[3] = 'F';
  hdr.frame_version = 1;
  hdr.frame_type = type;
  hdr.header_length = SDRF_HEADER_LEN;
  size_t sid_len = strlen(session_id);
  if (sid_len > sizeof(hdr.session_id)) sid_len = sizeof(hdr.session_id);
  memcpy(hdr.session_id, session_id, sid_len);
  hdr.chunk_index = chunk_index;
  hdr.byte_offset = offset;
  hdr.payload_length = payload_len;
  hdr.total_file_size = total_size;
  hdr.payload_checksum = payload && payload_len ? recCrc32Update(0, payload, payload_len) : 0;
  hdr.flags = flags;
  hdr.header_crc32 = 0;
  hdr.header_crc32 = recCrc32Update(0, (const uint8_t *)&hdr, sizeof(hdr));
  if (!recWriteBytes((uint8_t *)&hdr, sizeof(hdr))) return;
  if (payload && payload_len) recWriteBytes(payload, payload_len);
}

#if ENABLE_SD
static void sdWriteTask(void *) {
  Serial.printf("SD writer: core=%d priority=%u queue=%u batch=%u\n",
                xPortGetCoreID(), (unsigned)uxTaskPriorityGet(NULL),
                (unsigned)SD_QUEUE_DEPTH, (unsigned)SD_WRITE_BATCH_RECORDS);
  SdLogRecord batch[SD_WRITE_BATCH_RECORDS];
  uint32_t last_flush_ms = 0;
  while (true) {
    size_t batch_count = 0;
    if (g_sd_queue && xQueueReceive(g_sd_queue, &batch[batch_count], pdMS_TO_TICKS(100)) == pdTRUE) {
      batch_count = 1;
      while (batch_count < SD_WRITE_BATCH_RECORDS &&
             xQueueReceive(g_sd_queue, &batch[batch_count], 0) == pdTRUE) {
        batch_count++;
      }
      if (g_sd_mutex && xSemaphoreTake(g_sd_mutex, pdMS_TO_TICKS(50)) == pdTRUE) {
        if (g_sd_file) {
          const size_t bytes_to_write = batch_count * sizeof(SdLogRecord);
          uint32_t t0 = micros();
          size_t written = g_sd_file.write((uint8_t *)batch, bytes_to_write);
          uint32_t wu = (uint32_t)(micros() - t0);
          if (wu > g_max_sd_write_us) g_max_sd_write_us = wu;
          if (written == bytes_to_write) {
            g_sd_saved_samples += batch_count;
          } else {
            g_sd_write_errors += batch_count;
          }
        }
        xSemaphoreGive(g_sd_mutex);
      } else {
        g_sd_mutex_timeouts += batch_count;
      }
    }
#if SD_PERIODIC_FLUSH_MS > 0
    uint32_t now_ms = millis();
    if ((now_ms - last_flush_ms) >= SD_PERIODIC_FLUSH_MS) {
      last_flush_ms = now_ms;
      if (g_sd_mutex && xSemaphoreTake(g_sd_mutex, pdMS_TO_TICKS(50)) == pdTRUE) {
        if (g_sd_file) {
          uint32_t t0 = micros();
          g_sd_file.flush();
          uint32_t fu = (uint32_t)(micros() - t0);
          g_sd_flush_count++;
          if (fu > g_max_sd_flush_us) g_max_sd_flush_us = fu;
        }
        xSemaphoreGive(g_sd_mutex);
      } else {
        g_sd_mutex_timeouts++;
      }
    }
#endif
  }
}
#endif

static void logSd() {
#if ENABLE_SD
  if (!recLogGateOpen() || !g_sd_queue) return;
  SdLogRecord rec = {};
  rec.seq = seq;
  rec.sample_index = g_sd_record_sample_index;
  int64_t t_us = recNowUs();
  rec.time_us = t_us;
  memcpy(rec.ch, channels, sizeof(channels));
  if (xQueueSend(g_sd_queue, &rec, 0) != pdTRUE) {
    g_sd_queue_drops++;
  } else {
    g_sd_record_sample_index++;
    uint32_t depth = uxQueueMessagesWaiting(g_sd_queue);
    if (depth > g_sd_queue_max_depth) g_sd_queue_max_depth = depth;
  }
#endif
}

static bool sdEnsureReady() {
#if ENABLE_SD
  return g_sd_ready;
#else
  return false;
#endif
}

static bool sdRecordStart(const char *path_or_null, const char *requested_session) {
#if ENABLE_SD
  if (!sdEnsureReady()) {
    g_sd_begin_errors++;
    strncpy(g_rec_state, "failed", sizeof(g_rec_state) - 1);
    strncpy(g_last_rec_error, "sd_not_ready", sizeof(g_last_rec_error) - 1);
    controlPrintf("SD_STATUS enabled=1 ready=0 recording=0 error=begin_failed\n");
    return false;
  }

  if (g_sd_recording && g_sd_file) {
    g_sd_recording = false;
    if (g_sd_queue) while (uxQueueMessagesWaiting(g_sd_queue) > 0) vTaskDelay(pdMS_TO_TICKS(10));
    vTaskDelay(pdMS_TO_TICKS(30));
    if (g_sd_mutex) xSemaphoreTake(g_sd_mutex, portMAX_DELAY);
    g_sd_file.flush();
    g_sd_file.close();
    if (g_sd_mutex) xSemaphoreGive(g_sd_mutex);
  }

  makeSessionId(requested_session);
  if (path_or_null && path_or_null[0]) {
    strncpy(g_sd_path, path_or_null, sizeof(g_sd_path) - 1);
    g_sd_path[sizeof(g_sd_path) - 1] = '\0';
  } else {
    snprintf(g_sd_path, sizeof(g_sd_path), "/step_%s.bin", g_rec_session_id);
  }

  if (g_sd_mutex) xSemaphoreTake(g_sd_mutex, portMAX_DELAY);
  g_sd_file = SD.open(g_sd_path, FILE_WRITE);
  if (g_sd_mutex) xSemaphoreGive(g_sd_mutex);
  if (!g_sd_file) {
    g_sd_recording = false;
    g_sd_open_errors++;
    strncpy(g_rec_state, "failed", sizeof(g_rec_state) - 1);
    strncpy(g_last_rec_error, "open_failed", sizeof(g_last_rec_error) - 1);
    controlPrintf("SD_STATUS enabled=1 ready=1 recording=0 error=open_failed path=%s\n", g_sd_path);
    return false;
  }

  g_sd_saved_samples = 0;
  g_sd_record_sample_index = 0;
  g_sd_write_errors = 0;
  g_sd_queue_drops = 0;
  g_sd_header_errors = 0;
  g_sd_open_errors = 0;
  g_sd_begin_errors = 0;
  g_sd_mutex_timeouts = 0;
  g_sd_flush_count = 0;
  g_max_sd_write_us = 0;
  g_max_sd_flush_us = 0;
  g_sd_queue_max_depth = 0;
  g_final_file_size = 0;
  g_final_file_checksum = 0;
  strncpy(g_rec_state, g_rec_schedule_enabled ? "armed" : "starting", sizeof(g_rec_state) - 1);
  strncpy(g_transfer_state, "none", sizeof(g_transfer_state) - 1);
  strncpy(g_finalization_reason, "none", sizeof(g_finalization_reason) - 1);
  strncpy(g_last_rec_error, "none", sizeof(g_last_rec_error) - 1);

  SdLogHeader hdr = {};
  hdr.magic = SD_LOG_MAGIC;
  hdr.version = SD_LOG_VERSION;
  hdr.record_size = sizeof(SdLogRecord);
  hdr.sample_hz = g_sample_hz;
  hdr.channel_count = NUM_CHANNELS;
  g_sd_header_start_time_us = recNowUs();
  hdr.start_time_us = g_sd_header_start_time_us;
  hdr.header_size = sizeof(SdLogHeader);
  hdr.flags = g_rec_schedule_enabled ? SD_LOG_FLAG_SCHEDULED : 0;
  hdr.scheduled_start_time_us = g_rec_start_at_us;
  hdr.scheduled_stop_time_us = g_rec_stop_at_us;
  hdr.clock_offset_us = g_clock_offset_us;
  hdr.node_role = NODE_IS_MASTER ? SD_LOG_ROLE_MASTER : SD_LOG_ROLE_SLAVE;
  hdr.sync_valid = NODE_IS_MASTER ? 1 : (g_espnow_sync_received ? 1 : 0);
  hdr.reserved = 0;
  size_t written = 0;
  written = g_sd_file.write((uint8_t *)&hdr, sizeof(hdr));
  if (written != sizeof(hdr)) {
    g_sd_header_errors++;
  }

  g_sd_recording = true;
  if (g_rec_schedule_enabled && g_rec_start_at_us > 0) {
    g_rec_armed = true;
    strncpy(g_rec_state, "armed", sizeof(g_rec_state) - 1);
  } else {
    g_rec_armed = false;
    strncpy(g_rec_state, "recording", sizeof(g_rec_state) - 1);
  }
  controlPrintf("SD_STATUS enabled=1 ready=1 recording=1 path=%s sample_hz=%u\n",
                g_sd_path, (unsigned)g_sample_hz);
  return true;
#else
  controlPrintf("SD_STATUS enabled=0 ready=0 recording=0 error=compile_disabled\n");
  return false;
#endif
}

static void sdRewriteHeaderMetadata() {
#if ENABLE_SD
  if (!g_sd_file) return;
  SdLogHeader hdr = {};
  hdr.magic = SD_LOG_MAGIC;
  hdr.version = SD_LOG_VERSION;
  hdr.record_size = sizeof(SdLogRecord);
  hdr.sample_hz = g_sample_hz;
  hdr.channel_count = NUM_CHANNELS;
  hdr.start_time_us = g_sd_header_start_time_us;
  hdr.header_size = sizeof(SdLogHeader);
  hdr.flags = g_rec_schedule_enabled ? SD_LOG_FLAG_SCHEDULED : 0;
  hdr.scheduled_start_time_us = g_rec_start_at_us;
  hdr.scheduled_stop_time_us = g_rec_stop_at_us;
  hdr.clock_offset_us = g_clock_offset_us;
  hdr.node_role = NODE_IS_MASTER ? SD_LOG_ROLE_MASTER : SD_LOG_ROLE_SLAVE;
  hdr.sync_valid = NODE_IS_MASTER ? 1 : (g_espnow_sync_received ? 1 : 0);
  hdr.reserved = 0;
  if (!g_sd_file.seek(0) || g_sd_file.write((uint8_t *)&hdr, sizeof(hdr)) != sizeof(hdr)) {
    g_sd_header_errors++;
  }
  g_sd_file.seek(g_sd_file.size());
#endif
}

static void sdRecordStop() {
#if ENABLE_SD
  strncpy(g_rec_state, "finalizing", sizeof(g_rec_state) - 1);
  g_sd_recording = false;
  g_rec_armed = false;
  if (g_sd_queue) while (uxQueueMessagesWaiting(g_sd_queue) > 0) vTaskDelay(pdMS_TO_TICKS(10));
  vTaskDelay(pdMS_TO_TICKS(30));
  if (g_sd_mutex) xSemaphoreTake(g_sd_mutex, portMAX_DELAY);
  if (g_sd_file) {
    sdRewriteHeaderMetadata();
    uint32_t t0 = micros();
    g_sd_file.flush();
    uint32_t fu = (uint32_t)(micros() - t0);
    g_sd_flush_count++;
    if (fu > g_max_sd_flush_us) g_max_sd_flush_us = fu;
    g_sd_file.close();
  }
  if (g_sd_mutex) xSemaphoreGive(g_sd_mutex);
  controlPrintf("SD_FINAL ready=%d recording=0 path=%s saved=%llu errors=%llu queue_drops=%llu write_errors=%llu header_errors=%llu open_errors=%llu begin_errors=%llu mutex_timeouts=%llu max_queue_depth=%lu max_sd_write_us=%lu flush_count=%llu max_flush_us=%lu overrun=%lu\n",
                g_sd_ready ? 1 : 0,
                g_sd_path,
                (unsigned long long)g_sd_saved_samples,
                (unsigned long long)sdErrorTotal(),
                (unsigned long long)g_sd_queue_drops,
                (unsigned long long)g_sd_write_errors,
                (unsigned long long)g_sd_header_errors,
                (unsigned long long)g_sd_open_errors,
                (unsigned long long)g_sd_begin_errors,
                (unsigned long long)g_sd_mutex_timeouts,
                (unsigned long)g_sd_queue_max_depth,
                (unsigned long)g_max_sd_write_us,
                (unsigned long long)g_sd_flush_count,
                (unsigned long)g_max_sd_flush_us,
                (unsigned long)g_loop_overruns);
  g_final_file_checksum = checksumSdFile(g_sd_path, &g_final_file_size);
  if (strcmp(g_finalization_reason, "none") == 0) {
    strncpy(g_finalization_reason, "manual_stop", sizeof(g_finalization_reason) - 1);
  }
  strncpy(g_rec_state, "finalized", sizeof(g_rec_state) - 1);
  g_rec_schedule_enabled = false;
  g_rec_grace_deadline_ms = 0;
  controlPrintf("SD_STATUS enabled=1 ready=%d recording=0 path=%s saved=%llu errors=%llu queue_drops=%llu write_errors=%llu header_errors=%llu open_errors=%llu begin_errors=%llu mutex_timeouts=%llu max_queue_depth=%lu max_sd_write_us=%lu flush_count=%llu max_flush_us=%lu\n",
                g_sd_ready ? 1 : 0,
                g_sd_path,
                (unsigned long long)g_sd_saved_samples,
                (unsigned long long)sdErrorTotal(),
                (unsigned long long)g_sd_queue_drops,
                (unsigned long long)g_sd_write_errors,
                (unsigned long long)g_sd_header_errors,
                (unsigned long long)g_sd_open_errors,
                (unsigned long long)g_sd_begin_errors,
                (unsigned long long)g_sd_mutex_timeouts,
                (unsigned long)g_sd_queue_max_depth,
                (unsigned long)g_max_sd_write_us,
                (unsigned long long)g_sd_flush_count,
                (unsigned long)g_max_sd_flush_us);
#else
  controlPrintf("SD_STATUS enabled=0 ready=0 recording=0 error=compile_disabled\n");
#endif
}

static void relayDebugAppend(const char *event, const char *detail = "") {
#if ENABLE_SD
  if (!g_sd_ready) return;
  File f = SD.open("/relay_debug.txt", FILE_WRITE);
  if (!f) return;
  f.printf("%lu %s%s%s session=%s path=%s saved=%llu errors=%llu drops=%llu write_errors=%llu open_errors=%llu begin_errors=%llu state=%s\n",
           (unsigned long)millis(),
           event,
           detail && detail[0] ? " " : "",
           detail ? detail : "",
           g_rec_session_id,
           g_sd_path,
           (unsigned long long)g_sd_saved_samples,
           (unsigned long long)sdErrorTotal(),
           (unsigned long long)g_sd_queue_drops,
           (unsigned long long)g_sd_write_errors,
           (unsigned long long)g_sd_open_errors,
           (unsigned long long)g_sd_begin_errors,
           g_rec_state);
  f.close();
#else
  (void)event;
  (void)detail;
#endif
}

static void printAcqStatus() {
  Serial.printf("STATUS profile=%s cpu_mhz=%d seq=%lu generated=%llu sample_hz=%u filter=%d streaming=%d "
                "icm_ok=%d mag_ok=%d "
                "sd_enabled=%d sd_ready=%d sd_recording=%d sd_saved=%llu sd_errors=%llu "
                "queue_drops=%llu write_errors=%llu header_errors=%llu open_errors=%llu begin_errors=%llu "
                "mutex_timeouts=%llu max_queue_depth=%lu max_sd_write_us=%lu flush_count=%llu max_flush_us=%lu "
                "spi_mutex_timeouts=%llu max_loop_us=%lu loop_overruns=%lu "
                "stream_offered=%llu stream_enqueued=%llu stream_sent=%llu "
                "stream_queue_drops=%llu stream_send_errors=%llu "
                "stream_max_queue_depth=%lu max_stream_send_us=%lu "
                "prof_n=%llu "
                "avg_imu_us=%lu max_imu_us=%lu "
                "avg_mag_us=%lu max_mag_us=%lu "
                "avg_vqf_us=%lu max_vqf_us=%lu "
                "avg_vqf_mag_us=%lu max_vqf_mag_us=%lu "
                "avg_quat_us=%lu max_quat_us=%lu "
                "avg_serial_us=%lu max_serial_us=%lu\n",
                STEP_PROFILE_NAME,
                getCpuFrequencyMhz(),
                (unsigned long)seq,
                (unsigned long long)g_generated_samples,
                (unsigned)g_sample_hz,
                g_filter_on ? 1 : 0,
                streaming ? 1 : 0,
                icm_ok ? 1 : 0,
                mag_ok ? 1 : 0,
#if ENABLE_SD
                1,
#else
                0,
#endif
                g_sd_ready ? 1 : 0,
                g_sd_recording ? 1 : 0,
                (unsigned long long)g_sd_saved_samples,
                (unsigned long long)sdErrorTotal(),
                (unsigned long long)g_sd_queue_drops,
                (unsigned long long)g_sd_write_errors,
                (unsigned long long)g_sd_header_errors,
                (unsigned long long)g_sd_open_errors,
                (unsigned long long)g_sd_begin_errors,
                (unsigned long long)g_sd_mutex_timeouts,
                (unsigned long)g_sd_queue_max_depth,
                (unsigned long)g_max_sd_write_us,
                (unsigned long long)g_sd_flush_count,
                (unsigned long)g_max_sd_flush_us,
                (unsigned long long)g_spi_mutex_timeouts,
                (unsigned long)g_max_loop_us,
                (unsigned long)g_loop_overruns,
                (unsigned long long)g_stream_offered,
                (unsigned long long)g_stream_enqueued,
                (unsigned long long)g_stream_sent,
                (unsigned long long)g_stream_queue_drops,
                (unsigned long long)g_stream_send_errors,
                (unsigned long)g_stream_queue_max_depth,
                (unsigned long)g_max_stream_send_us,
                (unsigned long long)g_prof_samples,
                (unsigned long)profAvg(g_prof_imu_sum_us),
                (unsigned long)g_prof_imu_max_us,
                (unsigned long)profAvg(g_prof_mag_sum_us),
                (unsigned long)g_prof_mag_max_us,
                (unsigned long)profAvg(g_prof_vqf_sum_us),
                (unsigned long)g_prof_vqf_max_us,
                (unsigned long)profAvg(g_prof_vqf_mag_sum_us),
                (unsigned long)g_prof_vqf_mag_max_us,
                (unsigned long)profAvg(g_prof_quat_sum_us),
                (unsigned long)g_prof_quat_max_us,
                (unsigned long)profAvg(g_prof_serial_sum_us),
                (unsigned long)g_prof_serial_max_us);
#if ENABLE_ESPNOW
  Serial.printf("ESPNOW role=%s ch=%d sync=%d offset_us=%lld last_seq=%lu\n",
                NODE_IS_MASTER ? "master" : "slave",
                ESPNOW_WIFI_CHANNEL,
                g_espnow_sync_received ? 1 : 0,
                (long long)g_clock_offset_us,
                (unsigned long)g_espnow_last_seq);
#endif
}

static void recReplyToHost(const char *text);

static void printRecStatus() {
  char buf[2048];
  snprintf(buf, sizeof(buf),
                "REC STATUS_OK protocol=rec-v1 capabilities=record_control,status_v1,finalized_metadata,chunk_transfer_v1,whole_file_checksum,reconnect_grace,transfer_isolation=paused_isolated_stream transport=usb_bridge sd_ready=%d sd_open=%d recording_state=%s schedule_armed=%d start_at_time_us=%lld stop_at_time_us=%lld schedule_error=%s transfer_state=%s session_id=%s sd_path_token=sd:%s generated_samples=%llu saved_samples=%llu queue_drops=%llu write_errors=%llu header_errors=%llu open_errors=%llu begin_errors=%llu mutex_timeouts=%llu max_queue_depth=%lu max_write_latency_us=%lu flush_count=%llu max_flush_us=%lu overrun_count=%lu finalization_reason=%s file_byte_size=%llu file_checksum=%08lx checksum_type=crc32 last_error=%s grace_ms_remaining=%lu local_result_path=unknown local_analyzer_result=unknown\n",
                g_sd_ready ? 1 : 0,
                g_sd_recording ? 1 : 0,
                g_rec_state,
                g_rec_armed ? 1 : 0,
                (long long)g_rec_start_at_us,
                (long long)g_rec_stop_at_us,
                g_last_schedule_error,
                g_transfer_state,
                g_rec_session_id,
                g_rec_session_id,
                (unsigned long long)g_generated_samples,
                (unsigned long long)g_sd_saved_samples,
                (unsigned long long)g_sd_queue_drops,
                (unsigned long long)g_sd_write_errors,
                (unsigned long long)g_sd_header_errors,
                (unsigned long long)g_sd_open_errors,
                (unsigned long long)g_sd_begin_errors,
                (unsigned long long)g_sd_mutex_timeouts,
                (unsigned long)g_sd_queue_max_depth,
                (unsigned long)g_max_sd_write_us,
                (unsigned long long)g_sd_flush_count,
                (unsigned long)g_max_sd_flush_us,
                (unsigned long)g_loop_overruns,
                g_finalization_reason,
                (unsigned long long)g_final_file_size,
                (unsigned long)g_final_file_checksum,
                g_last_rec_error,
                (unsigned long)recGraceRemainingMs());
  recReplyToHost(buf);
}

static void replyToHost(const char *text) {
#if ENABLE_TCP && !ENABLE_SERIAL_BENCH
  tcpWriteBytes((const uint8_t *)text, strlen(text), TCP_WRITE_TIMEOUT_MS);
#else
  (void)text;  // Plugin USB path: bridge answers legacy handshakes on TCP.
#endif
}

static const char *identifyOutcomeName(uint8_t outcome) {
  switch (outcome) {
    case IDENTIFY_OUTCOME_CONFIRMED: return "confirmed";
    case IDENTIFY_OUTCOME_SENT_UNCONFIRMED: return "sent_unconfirmed";
    case IDENTIFY_OUTCOME_TIMEOUT: return "timeout";
    case IDENTIFY_OUTCOME_OFFLINE: return "offline";
    case IDENTIFY_OUTCOME_UNSUPPORTED: return "unsupported";
    case IDENTIFY_OUTCOME_REJECTED: return "rejected";
    case IDENTIFY_OUTCOME_INVALID_TARGET: return "invalid_target";
    default: return "rejected";
  }
}

static IdentifyAckPacket makeIdentifyAck(const IdentifyRequestPacket &request,
                                         uint8_t outcome,
                                         uint32_t applied_duration_ms) {
  IdentifyAckPacket ack = {};
  ack.magic = IDENTIFY_PACKET_MAGIC;
  ack.type = IDENTIFY_ACK_TYPE;
  ack.version = IDENTIFY_PACKET_VERSION;
  ack.packet_size = sizeof(IdentifyAckPacket);
  strncpy(ack.command_id, request.command_id, sizeof(ack.command_id) - 1);
  memcpy(ack.target_mac, request.target_mac, 6);
  ack.requested_duration_ms = request.requested_duration_ms;
  ack.applied_duration_ms = applied_duration_ms;
  ack.outcome = outcome;
  return ack;
}

static void emitIdentifyHostResult(const IdentifyAckPacket &ack,
                                   const char *detail) {
  char target[20], line[320];
  formatCanonicalDeviceId(ack.target_mac, target, sizeof(target));
  const char *format =
      (ack.outcome == IDENTIFY_OUTCOME_CONFIRMED ||
       ack.outcome == IDENTIFY_OUTCOME_SENT_UNCONFIRMED)
          ? "IDENTIFY_ACK protocol=identify-v1 command_id=%s target=%s outcome=%s requested_duration_ms=%lu applied_duration_ms=%lu detail=%s\n"
          : "IDENTIFY_ERR protocol=identify-v1 command_id=%s target=%s outcome=%s requested_duration_ms=%lu applied_duration_ms=%lu detail=%s\n";
  snprintf(line, sizeof(line), format, ack.command_id, target,
           identifyOutcomeName(ack.outcome),
           (unsigned long)ack.requested_duration_ms,
           (unsigned long)ack.applied_duration_ms, detail);
  replyToHost(line);
}

static void sendIdentifyApplicationAck(const IdentifyAckPacket &ack) {
#if ENABLE_ESPNOW
  if (g_master_peer_registered) {
    esp_now_send(g_master_mac, (const uint8_t *)&ack, sizeof(ack));
  }
#else
  (void)ack;
#endif
}

static void deliverIdentifyAck(const IdentifyAckPacket &ack,
                               const char *detail,
                               bool from_espnow) {
  if (from_espnow) {
    sendIdentifyApplicationAck(ack);
  } else {
    emitIdentifyHostResult(ack, detail);
  }
}

static void emitImmediateIdentifyResult(const char *command_id,
                                        const uint8_t target_mac[6],
                                        uint32_t requested_duration_ms,
                                        uint8_t outcome,
                                        const char *detail) {
  IdentifyRequestPacket request = {};
  request.magic = IDENTIFY_PACKET_MAGIC;
  request.type = IDENTIFY_REQUEST_TYPE;
  request.version = IDENTIFY_PACKET_VERSION;
  request.packet_size = sizeof(IdentifyRequestPacket);
  strncpy(request.command_id, command_id, sizeof(request.command_id) - 1);
  memcpy(request.target_mac, target_mac, 6);
  request.requested_duration_ms = requested_duration_ms;
  emitIdentifyHostResult(makeIdentifyAck(request, outcome, 0), detail);
}

static bool isSafeIdentifyCommandId(const String &value) {
  if (value.length() < 1 || value.length() > IDENTIFY_COMMAND_ID_MAX) {
    return false;
  }
  for (size_t i = 0; i < value.length(); i++) {
    const char c = value.charAt(i);
    if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.')) {
      return false;
    }
  }
  return true;
}

static bool readIdentifyToken(const String &line, const char *key,
                              String *value) {
  const String prefix = String(key) + "=";
  int start = line.indexOf(prefix);
  if (start < 0 || (start > 0 && line.charAt(start - 1) != ' ')) return false;
  start += prefix.length();
  int end = line.indexOf(' ', start);
  if (end < 0) end = line.length();
  if (end <= start || line.indexOf(prefix, end) >= 0) return false;
  *value = line.substring(start, end);
  return true;
}

static int identifyHexNibble(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

static bool parseCanonicalDeviceId(const String &value, uint8_t mac[6]) {
  if (value.length() != 18 || !value.startsWith("esp32:")) return false;
  for (int i = 0; i < 6; i++) {
    const int hi = identifyHexNibble(value.charAt(6 + i * 2));
    const int lo = identifyHexNibble(value.charAt(7 + i * 2));
    if (hi < 0 || lo < 0) return false;
    mac[i] = (uint8_t)((hi << 4) | lo);
  }
  return true;
}

static bool parseIdentifyDuration(const String &value, uint32_t *duration_ms) {
  if (value.length() < 1 || value.length() > 5) return false;
  uint32_t parsed = 0;
  for (size_t i = 0; i < value.length(); i++) {
    const char c = value.charAt(i);
    if (c < '0' || c > '9') return false;
    parsed = parsed * 10u + (uint32_t)(c - '0');
  }
  if (parsed < IDENTIFY_DURATION_MIN_MS ||
      parsed > IDENTIFY_DURATION_MAX_MS) {
    return false;
  }
  *duration_ms = parsed;
  return true;
}

static void dispatchIdentifyRequest(const char *command_id,
                                    const uint8_t target_mac[6],
                                    uint32_t requested_duration_ms) {
  IdentityPacket self = {};
  readLocalIdentity(&self);
  if (memcmp(self.base_mac, target_mac, 6) != 0) {
    emitImmediateIdentifyResult(command_id, target_mac, requested_duration_ms,
                                IDENTIFY_OUTCOME_INVALID_TARGET,
                                "not_session_self");
    return;
  }

  IdentifyRequestPacket request = {};
  request.magic = IDENTIFY_PACKET_MAGIC;
  request.type = IDENTIFY_REQUEST_TYPE;
  request.version = IDENTIFY_PACKET_VERSION;
  request.packet_size = sizeof(IdentifyRequestPacket);
  strncpy(request.command_id, command_id, sizeof(request.command_id) - 1);
  memcpy(request.target_mac, target_mac, 6);
  request.requested_duration_ms = requested_duration_ms;
  if (g_identify_request_pending) {
    const bool duplicate_pending =
        strcmp(request.command_id,
               g_identify_pending_request.command_id) == 0 &&
        memcmp(request.target_mac,
               g_identify_pending_request.target_mac, 6) == 0;
    emitImmediateIdentifyResult(
        command_id, target_mac, requested_duration_ms,
        duplicate_pending ? IDENTIFY_OUTCOME_SENT_UNCONFIRMED
                          : IDENTIFY_OUTCOME_REJECTED,
        duplicate_pending ? "queued_local" : "pending_busy");
    return;
  }
  g_identify_pending_request = request;
  g_identify_pending_from_espnow = false;
  g_identify_request_pending = true;
  emitImmediateIdentifyResult(command_id, target_mac, requested_duration_ms,
                              IDENTIFY_OUTCOME_SENT_UNCONFIRMED,
                              "queued_local");
}

static void handleIdentifyLine(const String &line) {
  // Contract: IDENTIFY protocol=identify-v1 command_id=<token>
  // target=esp32:<12hex> duration_ms=<1000-5000>.
  String protocol, command_id, target, duration_text;
  uint8_t target_mac[6] = {};
  uint32_t duration_ms = IDENTIFY_DURATION_DEFAULT_MS;
  const bool protocol_ok =
      readIdentifyToken(line, "protocol", &protocol) &&
      protocol == "identify-v1";
  const bool command_ok =
      readIdentifyToken(line, "command_id", &command_id) &&
      isSafeIdentifyCommandId(command_id);
  const bool target_ok =
      readIdentifyToken(line, "target", &target) &&
      parseCanonicalDeviceId(target, target_mac);
  const bool duration_present = line.indexOf(" duration_ms=") >= 0;
  const bool duration_token_ok =
      readIdentifyToken(line, "duration_ms", &duration_text);
  const bool duration_ok =
      !duration_present ||
      (duration_token_ok &&
       parseIdentifyDuration(duration_text, &duration_ms));

  if (!target_ok) {
    emitImmediateIdentifyResult(command_ok ? command_id.c_str() : "invalid",
                                target_mac, duration_ms,
                                IDENTIFY_OUTCOME_INVALID_TARGET,
                                "target_format");
  } else if (!protocol_ok || !command_ok || !duration_ok) {
    emitImmediateIdentifyResult(command_ok ? command_id.c_str() : "invalid",
                                target_mac, duration_ms,
                                IDENTIFY_OUTCOME_REJECTED,
                                !protocol_ok ? "protocol" :
                                (!command_ok ? "command_id" : "duration_ms"));
  } else {
    dispatchIdentifyRequest(command_id.c_str(), target_mac, duration_ms);
  }
}

static void identifyTick() {
  const uint32_t now_ms = millis();
  if (g_identify_request_pending) {
    const IdentifyRequestPacket request = g_identify_pending_request;
    const bool from_espnow = g_identify_pending_from_espnow;
    g_identify_request_pending = false;
    if (g_identify_active &&
        strcmp(request.command_id, g_identify_active_command_id) == 0 &&
        memcmp(request.target_mac, g_identify_active_target, 6) == 0) {
      deliverIdentifyAck(g_identify_last_ack, "duplicate_active", from_espnow);
    } else if (g_identify_last_ack_valid &&
               strcmp(request.command_id,
                      g_identify_last_ack.command_id) == 0 &&
               memcmp(request.target_mac,
                      g_identify_last_ack.target_mac, 6) == 0) {
      deliverIdentifyAck(g_identify_last_ack, "duplicate_replay", from_espnow);
    } else {
#if !STEPESP_IDENTIFY_LED_VERIFIED
      const IdentifyAckPacket ack =
          makeIdentifyAck(request, IDENTIFY_OUTCOME_UNSUPPORTED, 0);
      g_identify_last_ack = ack;
      g_identify_last_ack_valid = true;
      deliverIdentifyAck(ack, "board_unverified", from_espnow);
#else
      if (!g_identify_active) {
        g_identify_prior_led_level =
            digitalRead(STEPESP_IDENTIFY_LED_PIN);
        pinMode(STEPESP_IDENTIFY_LED_PIN, OUTPUT);
      }
      g_identify_active = true;
      strncpy(g_identify_active_command_id, request.command_id,
              sizeof(g_identify_active_command_id) - 1);
      memcpy(g_identify_active_target, request.target_mac, 6);
      g_identify_deadline_ms = now_ms + request.requested_duration_ms;
      g_identify_last_toggle_ms = now_ms;
      g_identify_led_level = STEPESP_IDENTIFY_LED_ACTIVE_LEVEL;
      digitalWrite(STEPESP_IDENTIFY_LED_PIN, g_identify_led_level);
      const IdentifyAckPacket ack =
          makeIdentifyAck(request, IDENTIFY_OUTCOME_CONFIRMED,
                          request.requested_duration_ms);
      g_identify_last_ack = ack;
      g_identify_last_ack_valid = true;
      deliverIdentifyAck(ack, "started", from_espnow);
#endif
    }
  }

#if STEPESP_IDENTIFY_LED_VERIFIED
  if (g_identify_active &&
      (int32_t)(now_ms - g_identify_deadline_ms) >= 0) {
    digitalWrite(STEPESP_IDENTIFY_LED_PIN, g_identify_prior_led_level);
    g_identify_active = false;
  } else if (g_identify_active &&
             (uint32_t)(now_ms - g_identify_last_toggle_ms) >=
                 IDENTIFY_BLINK_INTERVAL_MS) {
    g_identify_last_toggle_ms = now_ms;
    g_identify_led_level =
        g_identify_led_level == STEPESP_IDENTIFY_LED_ACTIVE_LEVEL
            ? !STEPESP_IDENTIFY_LED_ACTIVE_LEVEL
            : STEPESP_IDENTIFY_LED_ACTIVE_LEVEL;
    digitalWrite(STEPESP_IDENTIFY_LED_PIN, g_identify_led_level);
  }
#endif
}

static void printIdentityInventory() {
  IdentityPacket self = {};
  readLocalIdentity(&self);
  char device_id[20], display_mac[18], base_mac[18], sta_mac[18];
  char ap_mac[18], espnow_mac[18], line[640];
  formatCanonicalDeviceId(self.base_mac, device_id, sizeof(device_id));
  formatDisplayMac(self.base_mac, display_mac, sizeof(display_mac));
  formatDisplayMac(self.base_mac, base_mac, sizeof(base_mac));
  formatDisplayMac(self.sta_mac, sta_mac, sizeof(sta_mac));
  formatDisplayMac(self.ap_mac, ap_mac, sizeof(ap_mac));
  formatDisplayMac(self.espnow_mac, espnow_mac, sizeof(espnow_mac));
  snprintf(
      line, sizeof(line),
      "IDENTITY_OK protocol=id-v1 record=self peer_count=0 "
      "device_id=%s display_mac=%s base_mac=%s sta_mac=%s ap_mac=%s "
      "espnow_mac=%s role=slave route_ip=%s schema_version=%u verified=1 "
      "identify_supported=%u board_revision=%s\n",
      device_id, display_mac, base_mac, sta_mac, ap_mac, espnow_mac,
      g_cached_route_ip, (unsigned)self.version,
      (unsigned)((self.capabilities & IDENTITY_CAP_IDENTIFY) != 0),
      STEPESP_IDENTIFY_LED_BOARD_REVISION);
  replyToHost(line);
  replyToHost("IDENTITY_END protocol=id-v1 peer_count=0\n");
}

static void printSignalStatus() {
  IdentityPacket self = {};
  readLocalIdentity(&self);
  char device_id[20], line[420];
  formatCanonicalDeviceId(self.base_mac, device_id, sizeof(device_id));
  snprintf(
      line, sizeof(line),
      "SIGNAL_STATUS_OK protocol=signal-cap-v1 device_id=%s "
      "accel=%u gyro=%u magnetometer=%u quaternion=%u "
      "magnetometer_model=AK09916 magnetometer_sensitivity_uT_per_count=0.15 "
      "sequence_transport=none acquisition_clock=none\n",
      device_id, (unsigned)(icm_ok ? 1 : 0), (unsigned)(icm_ok ? 1 : 0),
      (unsigned)(mag_ok ? 1 : 0),
      (unsigned)((icm_ok && g_filter_on) ? 1 : 0));
  replyToHost(line);
}

static void recReplyToHost(const char *text) {
#if ENABLE_TCP && !ENABLE_SERIAL_BENCH
  tcpWriteBytes((const uint8_t *)text, strlen(text), TCP_WRITE_TIMEOUT_MS);
#else
  Serial.print(text);
#endif
}

static bool recFieldValue(const String &line, const char *key, char *buf, size_t len) {
  String needle = String(key) + "=";
  int start = line.indexOf(needle);
  if (start < 0 || len == 0) return false;
  start += needle.length();
  int end = line.indexOf(' ', start);
  if (end < 0) end = line.length();
  String value = line.substring(start, end);
  value.toCharArray(buf, len);
  return true;
}

#define replyToHost recReplyToHost
static void handleRecLine(const String &line) {
  if (line.startsWith("REC HELLO")) {
    if (line.indexOf("protocol_min=rec-v1") < 0) {
      replyToHost("REC ERR code=unsupported_protocol retryable=false detail=protocol_min\n");
      return;
    }
    recMarkControlConnected();
    char buf[320];
    snprintf(buf, sizeof(buf),
             "REC HELLO_OK protocol=rec-v1 firmware=arduino-step-%s transport=usb_bridge capabilities=record_control,status_v1,finalized_metadata,chunk_transfer_v1,whole_file_checksum,reconnect_grace,transfer_isolation=paused_isolated_stream max_chunk=%lu analyzer=sd-bin-v2 grace_ms=%lu\n",
             FIRMWARE_VERSION, (unsigned long)REC_MAX_CHUNK, (unsigned long)REC_RECONNECT_GRACE_MS);
    replyToHost(buf);
    return;
  }

  if (line.startsWith("REC START")) {
    char requested_session[sizeof(g_rec_session_id)] = {};
    recFieldValue(line, "requested_session", requested_session, sizeof(requested_session));

    if (g_sd_recording) {
      char err[128];
      snprintf(err, sizeof(err), "REC ERR code=already_recording session_id=%s retryable=false detail=active\n", g_rec_session_id);
      replyToHost(err);
      return;
    }
    bool ok = sdRecordStart(nullptr, requested_session);
    if (!ok) {
      replyToHost("REC ERR code=sd_not_ready retryable=true detail=start_failed\n");
      return;
    }
    char buf[192];
    snprintf(buf, sizeof(buf),
             "REC STARTED session_id=%s sd_path_token=sd:%s recording_state=recording generated_samples=%llu saved_samples=%llu\n",
             g_rec_session_id, g_rec_session_id,
             (unsigned long long)g_generated_samples,
             (unsigned long long)g_sd_saved_samples);
    replyToHost(buf);
    return;
  }

  if (line.startsWith("REC STATUS")) {
    printRecStatus();
    return;
  }

  if (line.startsWith("REC STOP")) {
    if (!g_sd_recording) {
      char err[128];
      snprintf(err, sizeof(err), "REC ERR code=not_recording session_id=%s retryable=false detail=idle\n", g_rec_session_id);
      replyToHost(err);
      return;
    }
    strncpy(g_finalization_reason, "manual_stop", sizeof(g_finalization_reason) - 1);
    char buf[96];
    snprintf(buf, sizeof(buf), "REC FINALIZING session_id=%s\n", g_rec_session_id);
    replyToHost(buf);
    sdRecordStop();
    snprintf(buf, sizeof(buf), "REC FINALIZED session_id=%s\n", g_rec_session_id);
    replyToHost(buf);
    return;
  }

  if (line.startsWith("REC SESSION")) {
    if (g_sd_recording) {
      replyToHost("REC ERR code=busy_recording retryable=true detail=session\n");
      return;
    }
    if (strcmp(g_rec_state, "finalized") != 0 || strcmp(g_rec_session_id, "none") == 0) {
      replyToHost("REC ERR code=not_found retryable=false detail=session\n");
      return;
    }
    char buf[256];
    snprintf(buf, sizeof(buf),
             "REC SESSION_OK session_id=%s sd_path_token=sd:%s file_size=%llu file_checksum=%08lx checksum_type=crc32 sample_count=%llu finalized_at=unknown finalization_reason=%s analyzer_format=sd-bin-v2\n",
             g_rec_session_id, g_rec_session_id,
             (unsigned long long)g_final_file_size,
             (unsigned long)g_final_file_checksum,
             (unsigned long long)g_sd_saved_samples,
             g_finalization_reason);
    replyToHost(buf);
    return;
  }

  if (line.startsWith("REC GET")) {
    if (g_sd_recording) {
      replyToHost("REC ERR code=busy_recording retryable=true detail=active\n");
      return;
    }
    if (strcmp(g_rec_state, "finalized") != 0) {
      replyToHost("REC ERR code=not_finalized retryable=true detail=session\n");
      return;
    }
    char off_buf[24], len_buf[16], idx_buf[16];
    uint64_t offset = recFieldValue(line, "offset", off_buf, sizeof(off_buf)) ? strtoull(off_buf, nullptr, 10) : 0;
    uint32_t length = recFieldValue(line, "length", len_buf, sizeof(len_buf)) ? (uint32_t)strtoul(len_buf, nullptr, 10) : REC_MAX_CHUNK;
    uint32_t chunk_index = recFieldValue(line, "chunk_index", idx_buf, sizeof(idx_buf)) ? (uint32_t)strtoul(idx_buf, nullptr, 10) : 0;
    if (offset > g_final_file_size) {
      replyToHost("REC ERR code=offset_out_of_range retryable=false detail=offset\n");
      return;
    }
    if (length > REC_MAX_CHUNK) length = REC_MAX_CHUNK;
    if (offset + length > g_final_file_size) length = (uint32_t)(g_final_file_size - offset);
    File f = SD.open(g_sd_path, FILE_READ);
    if (!f) {
      replyToHost("REC ERR code=sd_error retryable=true detail=read\n");
      return;
    }
    if (!f.seek(offset)) {
      f.close();
      replyToHost("REC ERR code=offset_out_of_range retryable=false detail=seek\n");
      return;
    }
    uint8_t buf[REC_MAX_CHUNK];
    size_t got = f.read(buf, length);
    f.close();
    strncpy(g_transfer_state, "chunking", sizeof(g_transfer_state) - 1);
    g_transfer_active = true;
    writeSdrfFrame(g_rec_session_id, SDRF_TYPE_DATA, chunk_index, offset, buf, got,
                   g_final_file_size, offset + got >= g_final_file_size ? 0x04 : 0);
    if (offset + got >= g_final_file_size) {
      writeSdrfFrame(g_rec_session_id, SDRF_TYPE_EOF, chunk_index + 1, g_final_file_size,
                     nullptr, 0, g_final_file_size, 0);
    }
    g_transfer_active = false;
    return;
  }

  if (line.startsWith("REC COMPLETE")) {
    strncpy(g_transfer_state, "complete", sizeof(g_transfer_state) - 1);
    char buf[96];
    snprintf(buf, sizeof(buf), "REC COMPLETE_OK session_id=%s transfer_state=complete\n", g_rec_session_id);
    replyToHost(buf);
    return;
  }

  if (line.startsWith("REC ABORT")) {
    strncpy(g_transfer_state, "aborted", sizeof(g_transfer_state) - 1);
    char buf[96];
    snprintf(buf, sizeof(buf), "REC ABORTED session_id=%s transfer_state=aborted\n", g_rec_session_id);
    replyToHost(buf);
    return;
  }

  if (line.startsWith("REC CLEAR")) {
    char scope[24];
    if (recFieldValue(line, "scope", scope, sizeof(scope)) && strcmp(scope, "errors") == 0) {
      strncpy(g_last_rec_error, "none", sizeof(g_last_rec_error) - 1);
      replyToHost("REC CLEAR_OK scope=errors\n");
      return;
    }
    if (recFieldValue(line, "scope", scope, sizeof(scope)) && strcmp(scope, "transfer") == 0) {
      strncpy(g_transfer_state, "none", sizeof(g_transfer_state) - 1);
      replyToHost("REC CLEAR_OK scope=transfer\n");
      return;
    }
    replyToHost("REC ERR code=invalid_scope retryable=false detail=clear\n");
    return;
  }

  replyToHost("REC ERR code=unsupported retryable=false detail=command\n");
}
#undef replyToHost

static void handleLine(const String &line) {
  if (line.equalsIgnoreCase("IDENTITY?")) {
    printIdentityInventory();
  } else if (line.equalsIgnoreCase("SIGNAL_STATUS?")) {
    printSignalStatus();
  } else if (line.startsWith("IDENTIFY ")) {
    handleIdentifyLine(line);
  } else if (line.startsWith("REC ")) {
    handleRecLine(line);
  } else if (line.startsWith("REDPITAYA")) {
    char buf[96];
    snprintf(buf, sizeof(buf),
             "%d channels; sample_rate=%u; node=esp32s3_arduino; filter=%s; transport=%s\n",
             NUM_CHANNELS, (unsigned)g_sample_hz, g_filter_on ? "on" : "off",
#if ENABLE_TCP
             WIFI_STREAM_OVER_TCP ? "tcp" : "udp"
#else
             "tcp"
#endif
    );
    replyToHost(buf);
    // NOTE: do NOT send a second "OK CHANNELS:N\n" — see step_node.ino comment.
  } else if (line.startsWith("FREQ:") || line.startsWith("FREQ ")) {
    int hz = parseFreqHz(line);
    if (!sampleHzValid(hz)) {
      replyToHost("ERROR FREQ: Hz must be >= 1\n");
    } else {
      applySampleRateHz(hz);
      char ok[32];
      snprintf(ok, sizeof(ok), "OK FREQ:%d\n", hz);
      replyToHost(ok);
#if !SERIAL_OUTPUT_BINARY
      Serial.printf("Sample rate set to %d Hz\n", hz);
#endif
    }
  } else if (line.startsWith("FILTER ON")) {
    g_filter_on = true;
    vqfReinitFilter();
    g_loop_overruns = 0;
    g_max_loop_us = 0;
    profReset();
    replyToHost("OK FILTER ON\n");
  } else if (line.startsWith("FILTER OFF")) {
    g_filter_on = false;
    g_loop_overruns = 0;
    g_max_loop_us = 0;
    profReset();
    replyToHost("OK FILTER OFF\n");
  } else if (line.startsWith("RECORD ON")) {
    g_loop_overruns = 0;
    g_max_loop_us   = 0;
    profReset();
    String path = line.substring(9);
    path.trim();
    sdRecordStart(path.length() ? path.c_str() : nullptr);
  } else if (line.startsWith("RECORD OFF")) {
    sdRecordStop();
  } else if (handleCfgLine(line)) {
    // handled
  } else if (line.startsWith("START")) {
    g_loop_overruns = 0;
    g_max_loop_us = 0;
    profReset();
    resetStreamStats();
#if ENABLE_TCP
    if (WIFI_STREAM_OVER_TCP)
      replyToHost("STARTED BIN:esp32s3_arduino transport=tcp\n");
    else
      replyToHost("STARTED BIN:esp32s3_arduino transport=udp port=55001\n");
#else
    replyToHost("STARTED BIN:esp32s3_arduino transport=tcp\n");
#endif
    replyToHost("SENSORS:0,ICM20948\n");
    // Complete the textual handshake before the writer task can put binary
    // frames on this same TCP socket.
    streaming = true;
#if !SERIAL_OUTPUT_BINARY
    Serial.printf("START accepted (USB: bridge streams; Wi-Fi: %s binary)\n",
                  WIFI_STREAM_OVER_TCP ? "TCP" : "UDP");
#endif
  } else if (line.startsWith("STOP")) {
    streaming = false;
    replyToHost("STOPPED\n");
  } else if (line.equalsIgnoreCase("AP?") || line.equalsIgnoreCase("WIFI?") ||
             line.equalsIgnoreCase("STATUS")) {
    printAcqStatus();
    printWifiStatus();
  }
}

static void pollSerialCommands() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line.length()) handleLine(line);
}

static const char *wifiStatusString(wl_status_t status) {
  switch (status) {
    case WL_IDLE_STATUS: return "WL_IDLE_STATUS";
    case WL_NO_SSID_AVAIL: return "WL_NO_SSID_AVAIL (SSID not found / wrong name / 5 GHz only?)";
    case WL_SCAN_COMPLETED: return "WL_SCAN_COMPLETED";
    case WL_CONNECTED: return "WL_CONNECTED";
    case WL_CONNECT_FAILED: return "WL_CONNECT_FAILED (wrong password?)";
    case WL_CONNECTION_LOST: return "WL_CONNECTION_LOST";
    case WL_DISCONNECTED: return "WL_DISCONNECTED (auth timeout / AP rejected / incompatible security?)";
    default: return "unknown";
  }
}

static void trimInPlace(char *s) {
  if (!s || !*s) return;
  char *start = s;
  while (*start == ' ' || *start == '\t') start++;
  if (start != s) memmove(s, start, strlen(start) + 1);
  size_t n = strlen(s);
  while (n > 0 && (s[n - 1] == ' ' || s[n - 1] == '\t')) s[--n] = '\0';
}

static volatile int lastStaDisconnectReason = -1;

static const char *wifiDisconnectReasonString(int reason) {
  switch (reason) {
    case 2: return "auth expire";
    case 15: return "4-way handshake timeout (wrong password?)";
    case 39: return "timeout";
    case 201: return "no AP found (SSID / 5 GHz only / hidden?)";
    case 202: return "auth fail (wrong password / WPA3-only AP?)";
    case 204: return "handshake timeout";
    case 205: return "group key update timeout";
    default: return "see esp_wifi_types.h WIFI_REASON_*";
  }
}

static void onWifiEvent(WiFiEvent_t event, WiFiEventInfo_t info) {
  if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
    lastStaDisconnectReason = info.wifi_sta_disconnected.reason;
    Serial.printf("\n[WiFi] STA disconnected reason=%d (%s)\n",
                  lastStaDisconnectReason,
                  wifiDisconnectReasonString(lastStaDisconnectReason));
  }
}

static void printWifiFailureHelp(wl_status_t status) {
  Serial.printf("Wi-Fi status=%d (%s)\n", (int)status, wifiStatusString(status));
  if (lastStaDisconnectReason >= 0) {
    Serial.printf("Last disconnect reason=%d (%s)\n",
                  lastStaDisconnectReason,
                  wifiDisconnectReasonString(lastStaDisconnectReason));
  }
  Serial.println("STA tips: 2.4 GHz hotspot band; correct SSID/password; PC and ESP32 same network;");
  Serial.println("  iPhone: Settings -> Personal Hotspot -> Maximize Compatibility ON");
}

static void printWifiStatus() {
  if (ENABLE_SERIAL_BENCH) {
    Serial.println("--- USB Open Ephys status ---");
    Serial.println("Wi-Fi TCP disabled; Open Ephys uses serial_tcp_bridge.py on the PC");
    Serial.println("Open Ephys Plugin AcqBoard: Node IP 127.0.0.1 port 5000");
    Serial.printf("Serial stream: %s  channels=%d  streaming=%s\n",
                  SERIAL_OUTPUT_BINARY ? "Open Ephys binary" : "CSV",
                  NUM_CHANNELS,
                  streaming ? "yes" : "no");
#if ENABLE_ESPNOW
    Serial.printf("ESP-NOW WiFi: STA mode ch=%d for sync only; no TCP/IP address expected\n",
                  ESPNOW_WIFI_CHANNEL);
#else
    Serial.println("ESP-NOW disabled; Wi-Fi radio off");
#endif
    Serial.println("Serial command: STATUS  (repeat)");
    return;
  }

  if (!wifi_up) {
    Serial.println("[WiFi] not up (USB mode or init failed)");
    return;
  }
  if (wifi_soft_ap) {
    Serial.println("--- Soft AP status ---");
    Serial.printf("SSID=%s  pass=%s  channel=%d  broadcast=ON  WPA2-PSK\n",
                  WIFI_AP_SSID, WIFI_AP_PASS, WIFI_AP_CHANNEL);
    Serial.printf("AP MAC=%s  IP=%s  TCP :%d\n",
                  WiFi.softAPmacAddress().c_str(),
                  WiFi.softAPIP().toString().c_str(), TCP_PORT);
    Serial.printf("Stations connected: %u / %d\n",
                  WiFi.softAPgetStationNum(), WIFI_AP_MAX_CONN);
  } else {
    Serial.println("--- STA status ---");
    Serial.printf("hostname=%s  STA MAC=%s\n",
                  WiFi.getHostname(), WiFi.macAddress().c_str());
    Serial.printf("IP=%s  gateway=%s  subnet=%s  RSSI=%d dBm\n",
                  WiFi.localIP().toString().c_str(),
                  WiFi.gatewayIP().toString().c_str(),
                  WiFi.subnetMask().toString().c_str(), WiFi.RSSI());
    Serial.printf("TCP listen :%d  client=%s  streaming=%s\n",
                  TCP_PORT,
                  (client.fd() >= 0) ? "yes" : "no",
                  streaming ? "yes" : "no");
    Serial.println("PC: ping IP above; Plugin/Ephys Socket -> IP:5000; send REDPITAYA then START");
  }
  Serial.println("Serial command: STATUS  (repeat)");
}

static bool startSoftApFallback() {
  WiFi.disconnect(true);
  WiFi.softAPdisconnect(true);
  delay(200);
  WiFi.mode(WIFI_OFF);
  delay(300);
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_TX_POWER_AP);
  WiFi.setMinSecurity(WIFI_AUTH_WPA_PSK);
  // Explicit AP IP — some Windows builds fail DHCP on softAP without this
  if (!WiFi.softAPConfig(IPAddress(192, 168, 4, 1), IPAddress(192, 168, 4, 1),
                         IPAddress(255, 255, 255, 0))) {
    Serial.println("[AP] softAPConfig failed (continuing)");
  }
  // hidden=0 → SSID broadcast ON; password ≥8 → WPA2-PSK
  bool ok = WiFi.softAP(WIFI_AP_SSID, WIFI_AP_PASS, WIFI_AP_CHANNEL, 0, WIFI_AP_MAX_CONN);
  if (!ok) {
    Serial.println("Soft AP start failed");
    return false;
  }
  delay(1500);  // let beacon stabilize before Windows scan
  wifi_soft_ap = true;
  markWifiUp();
  Serial.println("WiFi OK Soft AP started");
  printWifiStatus();
  Serial.println("PC: join Wi-Fi STEP_ESP32 (password step1234), then host 192.168.4.1:5000");
  return true;
}

static void setupWifi() {
  if (!useWifi()) {
    Serial.println("Wi-Fi skipped — USB serial bench mode");
    Serial.println("PC: host\\run_usb_plugin_bridge.ps1 COMx  (Plugin) or serial_tcp_bridge.py COMx");
    Serial.println("Open Ephys: 127.0.0.1:5000 — not ESP32 Wi-Fi IP");
    return;
  }

  if (WIFI_FORCE_SOFT_AP) {
    Serial.printf("Wi-Fi STA skipped — starting Soft AP %s\n", WIFI_AP_SSID);
    startSoftApFallback();
    return;
  }

  char ssid[33];
  char pass[64];
  strncpy(ssid, WIFI_SSID, sizeof(ssid) - 1);
  ssid[sizeof(ssid) - 1] = '\0';
  strncpy(pass, WIFI_PASS, sizeof(pass) - 1);
  pass[sizeof(pass) - 1] = '\0';
  trimInPlace(ssid);
  trimInPlace(pass);

  wifi_soft_ap = false;
  lastStaDisconnectReason = -1;
  WiFi.persistent(false);  // do not load stale NVS credentials / corrupt join state
  WiFi.onEvent(onWifiEvent);
  WiFi.disconnect(true);
  WiFi.softAPdisconnect(true);
  delay(200);
  WiFi.mode(WIFI_OFF);
  delay(200);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // iPhone hotspot: avoid ESP light-sleep during join
  WiFi.setTxPower(WIFI_TX_POWER_STA);
#if defined(WIFI_AUTH_WPA2_WPA3_PSK)
  WiFi.setMinSecurity(WIFI_AUTH_WPA2_WPA3_PSK);  // WPA2 + WPA3-only hotspots
#else
  WiFi.setMinSecurity(WIFI_AUTH_WPA_PSK);
#endif
  WiFi.setHostname(WIFI_HOSTNAME);

  if (strcmp(ssid, "YOUR_HOTSPOT") == 0) {
    Serial.println("WARNING: WIFI_SSID still \"YOUR_HOTSPOT\" — edit sketch before upload");
  }

  Serial.println("Scanning 2.4 GHz networks (3 s, hidden SSIDs included)...");
  int n = WiFi.scanNetworks(false, true);  // async=false, show_hidden=true
  bool ssid_seen = false;
  for (int i = 0; i < n; i++) {
    if (WiFi.SSID(i) == ssid) {
      ssid_seen = true;
      Serial.printf("  target \"%s\" seen RSSI=%d ch=%d\n",
                    ssid, WiFi.RSSI(i), WiFi.channel(i));
    }
  }
  if (n == 0) {
    Serial.println("  (no networks — RF/antenna/power issue?)");
  } else if (!ssid_seen) {
    Serial.printf("  \"%s\" NOT in scan — typo, 5 GHz-only, or out of range\n", ssid);
  }
  WiFi.scanDelete();

#if SLAVE_STATIC_IP_OCTET > 1
  WiFi.config(IPAddress(192,168,4,SLAVE_STATIC_IP_OCTET),
              IPAddress(192,168,4,1),
              IPAddress(255,255,255,0));
  Serial.printf("Static slave IP requested: 192.168.4.%u\n", (unsigned)SLAVE_STATIC_IP_OCTET);
#else
  Serial.println("Slave IP: DHCP from master AP (set SLAVE_STATIC_IP_OCTET per slave for fixed IPs)");
#endif

  if (strlen(pass) == 0) {
    Serial.printf("Connecting to open network \"%s\" len=%u (2.4 GHz)\n",
                  ssid, (unsigned)strlen(ssid));
    WiFi.begin(ssid);
  } else {
    Serial.printf("Connecting to \"%s\" len=%u (2.4 GHz)\n",
                  ssid, (unsigned)strlen(ssid));
    WiFi.begin(ssid, pass);
  }
  WiFi.setAutoReconnect(true);

  uint32_t t0 = millis();
  uint32_t lastStatusLog = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    uint32_t now = millis();
    wl_status_t st = WiFi.status();
    Serial.printf(". status=%d (%s)", (int)st, wifiStatusString(st));
    if (lastStaDisconnectReason >= 0) {
      Serial.printf(" disc_reason=%d (%s)",
                    lastStaDisconnectReason,
                    wifiDisconnectReasonString(lastStaDisconnectReason));
    }
    Serial.println();
    if (now - lastStatusLog >= 10000) {
      lastStatusLog = now;
      Serial.printf("  elapsed=%lu ms\n", (unsigned long)(now - t0));
    }
    if (now - t0 > (uint32_t)WIFI_STA_TIMEOUT_MS) {
      Serial.println();
      wl_status_t st = WiFi.status();
      printWifiFailureHelp(st);
      #if WIFI_ALLOW_SOFT_AP_FALLBACK
      Serial.printf("STA failed (status=%d) — starting Soft AP %s\n", (int)st, WIFI_AP_SSID);
      startSoftApFallback();
      #else
      // A slave SoftAP would duplicate the master's SSID and 192.168.4.1,
      // placing the slave on an unreachable network. Keep the STA attempt
      // alive; auto-reconnect will associate when the master becomes ready.
      Serial.printf("STA not connected (status=%d) — remaining STA-only and retrying %s\n",
                    (int)st, WIFI_SSID);
      markWifiUp();
      #endif
      return;
    }
  }

  wifi_soft_ap = false;
  markWifiUp();
  Serial.println();
  Serial.println("========================================");
  Serial.println("  WiFi STA CONNECTED — use this IP on PC");
  Serial.println("========================================");
  printWifiStatus();
  Serial.println("========================================");
}

static void setupEspNow() {
#if ENABLE_ESPNOW
  // When TCP is not in use, WiFi was not started by setupWifi().
  // ESP-NOW requires the WiFi stack to be initialized (STA mode, no AP join needed).
  if (!wifi_up) {
    WiFi.persistent(false);
    WiFi.disconnect(true);
    delay(100);
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(true);
    esp_wifi_set_channel(ESPNOW_WIFI_CHANNEL, WIFI_SECOND_CHAN_NONE);
    delay(100);
    markWifiUp();
    Serial.printf("ESP-NOW WiFi: STA mode ch=%d (no AP join, modem-sleep ON)\n", ESPNOW_WIFI_CHANNEL);
  }
  esp_err_t err = esp_now_init();
  if (err != ESP_OK) {
    Serial.printf("ESP-NOW init failed: %d\n", (int)err);
    return;
  }
  esp_now_register_recv_cb(onEspNowRecv);
  esp_now_register_send_cb(onEspNowSent);
  // Always register broadcast peer (needed for initial discovery and fallback)
  esp_now_peer_info_t peer = {};
  memset(peer.peer_addr, 0xFF, 6);
  peer.channel = ESPNOW_WIFI_CHANNEL;
  peer.ifidx = wifi_soft_ap ? WIFI_IF_AP : WIFI_IF_STA;
  peer.encrypt = false;
  err = esp_now_add_peer(&peer);
  if (err != ESP_OK) {
    Serial.printf("ESP-NOW add peer failed: %d\n", (int)err);
    return;
  }
  Serial.printf("ESP-NOW ready (role=%s ch=%d iface=%s unicast=%s)\n",
                NODE_IS_MASTER ? "master" : "slave",
                ESPNOW_WIFI_CHANNEL,
                wifi_soft_ap ? "AP" : "STA",
                ESPNOW_UNICAST ? "yes" : "no");
#else
  Serial.println("ESP-NOW disabled — single-node mode");
#endif
}

static void maybeRepeatStatus() {
#if REPEAT_STATUS_SEC > 0
#if ENABLE_SERIAL_BENCH && SERIAL_OUTPUT_BINARY
  // Text inserted after streaming starts would corrupt USB Open Ephys frames.
  return;
#endif
  if (millis() - last_status_ms < (uint32_t)REPEAT_STATUS_SEC * 1000UL) return;
  last_status_ms = millis();
  if (wifi_up) {
    printWifiStatus();
    return;
  }
  if (!icm_ok) {
    Serial.println("ICM20948: synthetic fallback - check 3V3, GND, SCK->D3, MISO->D5, MOSI->D4, CS->D6");
  }
  if (!mag_ok) {
    Serial.println("MAG unavailable: ch6-8=0, VQF 6-DOF only (no heading). See boot log for cause.");
  }
#endif
}

void setup() {
#ifdef STEP_CPU_MHZ
  setCpuFrequencyMhz(STEP_CPU_MHZ);
#endif
  Serial.begin(115200);
  delay(3000);
  while (!Serial && millis() < 5000) {
    delay(10);
  }

  Serial.println();
  Serial.printf("STEP node (Arduino) starting profile=%s CPU=%d MHz\n",
                STEP_PROFILE_NAME,
                getCpuFrequencyMhz());

  g_spi_mutex = xSemaphoreCreateMutex();
  g_tcp_mutex = xSemaphoreCreateMutex();

  initDio();

  printBootDiagnostics();
  icm_ok = initIcm20948();
  mag_ok = initAk09916();
  if (!mag_ok) {
    Serial.println("WARNING: AK09916 magnetometer not found.");
    Serial.println("  ch[6..8] will be 0; VQF quaternion is 6-DOF only (no yaw/heading).");
    Serial.println("  Causes: XIAO non-Sense variant (no AK09916); ICM SPI aux bus not reading");
    Serial.println("  (USER_CTRL); AK09916 needs power-cycle; board wiring missing SPI pins to ICM.");
  }

  setupWifi();
  setupEspNow();
#if ENABLE_TCP && !ENABLE_SERIAL_BENCH
  if (wifi_up) {
    server.begin();
    Serial.printf("TCP listen :%d\n", TCP_PORT);
  }
#endif

#if ENABLE_SD
  g_sd_mutex = xSemaphoreCreateMutex();
  g_sd_ready = SD.begin(PIN_SD_CS, SPI, 25000000);
  Serial.println(g_sd_ready ? "SD ready" : "SD init failed");
  relayDebugAppend(g_sd_ready ? "boot" : "boot_sd_failed",
                   g_sd_ready ? "sd_ready=1" : "sd_ready=0");
  g_sd_queue = xQueueCreate(SD_QUEUE_DEPTH, sizeof(SdLogRecord));
  if (g_sd_queue) {
    xTaskCreatePinnedToCore(sdWriteTask, "sd_write", 16384, NULL, SD_TASK_PRIORITY, NULL, 0);
  }
#endif

  g_stream_queue = xQueueCreate(STREAM_QUEUE_DEPTH, sizeof(StreamRecord));
  if (g_stream_queue) {
    xTaskCreatePinnedToCore(streamWriteTask, "stream_write", 8192, NULL,
                            STREAM_TASK_PRIORITY, NULL, 0);
  }
  Serial.printf("Acquisition loop: core=%d priority=%u\n",
                xPortGetCoreID(), (unsigned)uxTaskPriorityGet(NULL));

#if ENABLE_SERIAL_BENCH
  Serial.println("Serial bench active @115200");
  Serial.println(SERIAL_OUTPUT_BINARY
                     ? "Format: Open Ephys binary on Serial"
                     : "Format: CSV seq,ax,ay,az,gx,gy,gz,mx,my,mz,qw,qx,qy,qz,dio");
#endif

  boot_ms = millis();
  Serial.printf("CSV/stream paused %d ms — read diagnostics above\n", BOOT_CSV_DELAY_MS);
  last_status_ms = millis();
}

#if ENABLE_TCP && !ENABLE_SERIAL_BENCH
static char g_tcp_line[256];
static size_t g_tcp_line_len = 0;

static void pollTcpCommands() {
  const int sock = client.fd();
  if (sock < 0) {
    g_tcp_line_len = 0;
    return;
  }
  uint8_t tmp[128];
  const int n = recv(sock, tmp, sizeof(tmp), MSG_DONTWAIT);
  if (n == 0) {
    Serial.println("TCP peer closed; releasing client slot");
    streaming = false;
    stopTcpClient();
#if ENABLE_ESPNOW
    if (!g_espnow_sync_received)
      recMarkControlDisconnected();
#else
    recMarkControlDisconnected();
#endif
    g_stream_target_ip = 0;
    tcp_client_last_activity_ms = 0;
    g_tcp_line_len = 0;
    return;
  }
  if (n < 0) {
    return;
  }
  tcp_client_last_activity_ms = millis();
  for (int i = 0; i < n; i++) {
    const char c = (char)tmp[i];
    if (c == '\n') {
      g_tcp_line[g_tcp_line_len] = '\0';
      if (g_tcp_line_len > 0) {
        handleLine(String(g_tcp_line));
      }
      g_tcp_line_len = 0;
    } else if (c != '\r' && g_tcp_line_len + 1 < sizeof(g_tcp_line)) {
      g_tcp_line[g_tcp_line_len++] = c;
    }
  }
}
#endif

void loop() {
  pollSerialCommands();
  identifyTick();
#if ENABLE_ESPNOW
  if (g_espnow_rec_start_pending) {
    g_espnow_rec_start_pending = false;
    Serial.println("[RELAY] got REC_START from master");
    relayDebugAppend("got_rec_start");
    if (!g_sd_recording) {
      const int64_t start_at = g_espnow_requested_start_at_us;
      const int64_t stop_at = g_espnow_requested_stop_at_us;
      if (!g_espnow_sync_received) {
        recSetScheduleError("unsynced_start");
        strncpy(g_rec_state, "failed", sizeof(g_rec_state) - 1);
        Serial.println("[RELAY] REC_START rejected: no ESP-NOW clock sync");
        relayDebugAppend("sd_start_failed", "error=unsynced_start");
      } else if (start_at > 0 && recNowUs() > start_at - REC_SCHEDULE_MIN_LEAD_US) {
        recSetScheduleError("late_start");
        strncpy(g_rec_state, "failed", sizeof(g_rec_state) - 1);
        Serial.printf("[RELAY] REC_START rejected: late start_at=%lld now=%lld\n",
                      (long long)start_at, (long long)recNowUs());
        relayDebugAppend("sd_start_failed", "error=late_start");
      } else {
        g_rec_schedule_enabled = start_at > 0;
        g_rec_start_at_us = start_at;
        g_rec_stop_at_us = stop_at;
        g_rec_armed = false;
        strncpy(g_last_schedule_error, "none", sizeof(g_last_schedule_error) - 1);
        const bool ok = sdRecordStart(nullptr, g_espnow_requested_session);
        Serial.printf("[RELAY] sdRecordStart %s session=%s path=%s ready=%d\n",
                      ok ? "OK" : "FAILED",
                      g_rec_session_id,
                      g_sd_path,
                      g_sd_ready ? 1 : 0);
        if (!ok) recSetScheduleError("sd_start_failed");
        relayDebugAppend(ok ? "sd_start_ok" : "sd_start_failed");
      }
    } else {
      Serial.println("[RELAY] REC_START ignored; already recording");
      relayDebugAppend("sd_start_ignored", "already_recording=1");
    }
  }
  if (g_espnow_rec_stop_pending) {
    g_espnow_rec_stop_pending = false;
    Serial.println("[RELAY] got REC_STOP from master");
    relayDebugAppend("got_rec_stop");
    if (g_sd_recording) {
      const int64_t stop_at = g_espnow_requested_stop_at_us;
      if (stop_at > 0) {
        g_rec_schedule_enabled = true;
        g_rec_stop_at_us = stop_at;
        Serial.printf("[RELAY] REC_STOP scheduled stop_at=%lld now=%lld\n",
                      (long long)stop_at, (long long)recNowUs());
        relayDebugAppend("sd_stop_scheduled");
      } else {
        sdRecordStop();
        Serial.printf("[RELAY] sdRecordStop done session=%s saved=%llu errors=%llu path=%s\n",
                      g_rec_session_id,
                      (unsigned long long)g_sd_saved_samples,
                      (unsigned long long)sdErrorTotal(),
                      g_sd_path);
        relayDebugAppend("sd_stop_done");
      }
    } else {
      Serial.println("[RELAY] REC_STOP ignored; not recording");
      relayDebugAppend("sd_stop_ignored", "recording=0");
    }
  }
  // The master's ESP-NOW packets (periodic sync + commands) are this slave's
  // control link. Arm the 90 s reconnect grace when they go quiet (master
  // battery died / out of range); clear it as soon as they resume.
  if (g_espnow_sync_received) {
    if ((uint32_t)(millis() - g_espnow_last_rx_ms) > MASTER_SYNC_TIMEOUT_MS)
      recMarkControlDisconnected();
    else
      recMarkControlConnected();
  }
#endif
  recMaybeScheduledStop();
  recMaybeFinalizeTimeout();

#if ENABLE_TCP && !ENABLE_SERIAL_BENCH
  if (wifi_up) {
    if (g_tcp_reset_requested) {
      Serial.println("TCP stream write failed repeatedly; closing stale client");
      streaming = false;
      stopTcpClient();
#if ENABLE_ESPNOW
      if (!g_espnow_sync_received)
        recMarkControlDisconnected();
#else
      recMarkControlDisconnected();
#endif
      g_stream_target_ip = 0;
      tcp_client_last_activity_ms = 0;
    }
    if (client.fd() < 0) {
      // Only treat a missing TCP client as "host disconnected" when this
      // slave is NOT being driven over ESP-NOW; otherwise a recording started
      // by the master's relay would auto-finalize 90 s in even though the
      // master is alive.
#if ENABLE_ESPNOW
      if (!g_espnow_sync_received)
        recMarkControlDisconnected();
#else
      recMarkControlDisconnected();
#endif
      streaming = false;
      g_stream_target_ip = 0;
      WiFiClient incoming = server.available();
      if (incoming.fd() >= 0) {
        g_tcp_silent_accepts = 0;
        client = incoming;
        configureTcpClient(client);
        g_tcp_consecutive_write_failures = 0;
        g_tcp_reset_requested = false;
        streaming = false;
        g_stream_target_ip = (uint32_t)client.remoteIP();
        tcp_client_last_activity_ms = millis();
        g_tcp_line_len = 0;
        recMarkControlConnected();
        Serial.printf("Client connected from %s\n",
                      client.remoteIP().toString().c_str());
      }
    } else if (!streaming
               && tcp_client_last_activity_ms != 0
               && millis() - tcp_client_last_activity_ms > TCP_IDLE_CLIENT_TIMEOUT_MS) {
      Serial.println("TCP client idle before command; closing");
      stopTcpClient();
#if ENABLE_ESPNOW
      if (!g_espnow_sync_received)
        recMarkControlDisconnected();
#else
      recMarkControlDisconnected();
#endif
      g_stream_target_ip = 0;
      tcp_client_last_activity_ms = 0;
      g_tcp_line_len = 0;
    }
    pollTcpCommands();
  }
#endif

  maybeRepeatStatus();

  if (millis() - boot_ms < (uint32_t)BOOT_CSV_DELAY_MS) {
    return;
  }

  uint32_t now = micros();
  uint32_t loop_start_us = now;
  if (g_sample_hz < 1)
    return;
  const uint32_t period_us = 1000000UL / (uint32_t)g_sample_hz;
  if (g_sample_last_us != 0 && (uint32_t)(now - g_sample_last_us) < period_us)
    return;
  g_sample_last_us = now;

  int16_t imu[6];
  int16_t mag[3];
  bool mag_fresh = false;
  uint32_t prof_start_us = micros();
  readImu(imu);
  profAdd((uint32_t)(micros() - prof_start_us), &g_prof_imu_sum_us, &g_prof_imu_max_us);

  prof_start_us = micros();
  readMag(mag, &mag_fresh);
  profAdd((uint32_t)(micros() - prof_start_us), &g_prof_mag_sum_us, &g_prof_mag_max_us);

  updateDio();
  packChannelsFromImu(imu, mag_ok ? mag : nullptr, mag_fresh);

  sendEspNowSync();
  sendIdentityPacket();
  sendSlaveStatus();
  logSd();
  queueStreamRecord();

  g_generated_samples++;
  g_prof_samples++;
  uint32_t loop_us = (uint32_t)(micros() - loop_start_us);
  if (loop_us > g_max_loop_us) g_max_loop_us = loop_us;
  if (loop_us > period_us) g_loop_overruns++;

  seq++;
}
