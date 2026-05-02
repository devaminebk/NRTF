#ifndef CONFIG_H
#define CONFIG_H

// ===== WiFi Configuration =====
#define WIFI_SSID "Galaxy S20 Fe"
#define WIFI_PASSWORD "s20fe2004"

// ===== MQTT Configuration =====
#define MQTT_SERVER "192.168.20.15"  // Local Mosquitto broker on PC
#define MQTT_PORT 1883
#define MQTT_CLIENT_ID "ESP32_SENSOR_DEVICE"
#define MQTT_TOPIC_SENSORS "esp32/sensors"

// ===== Sensor Configuration =====
// DHT22 pins
#define DHT22_PIN 4

// Flame Sensor pins
#define FLAME_DIGITAL_PIN 5
#define FLAME_ANALOG_PIN 34

// ===== Timing Configuration (ms) =====
#define SENSOR_READ_INTERVAL 5000  // Read sensors every 5 seconds
#define MQTT_RECONNECT_INTERVAL 5000

// ===== MQTT Liveness =====
// Aggressive keepalive so half-open sockets are caught fast. With publishes
// every 5s and a TCP send buffer of several KB, a dead broker can otherwise
// silently absorb 20+ "successful" writes before the lib notices.
// Detection time = ~2 x MQTT_KEEPALIVE seconds (PINGREQ + PINGRESP timeout).
#define MQTT_KEEPALIVE      4
#define MQTT_SOCKET_TIMEOUT 2   // seconds before publish/connect calls give up

// ===== Offline Buffer Configuration =====
#define BUFFER_MAX_SIZE    20   // max readings kept while MQTT is down
#define PAYLOAD_MAX_LEN   512   // must be >= serialized JSON size

// ===== Data Validation Ranges =====
#define TEMP_MIN -40.0f
#define TEMP_MAX 80.0f
#define HUMIDITY_MIN 0.0f
#define HUMIDITY_MAX 100.0f
#define FLAME_ANALOG_MIN 0
#define FLAME_ANALOG_MAX 4095

#endif
