#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "sensor_manager.h"
#include "message_buffer.h"
#include "sensors/dht22_sensor.h"
#include "sensors/flame_sensor.h"

// ===== Global Objects =====
WiFiClient espClient;
PubSubClient mqttClient(espClient);
SensorManager sensorManager;
MessageBuffer messageBuffer;

// ===== Timing Variables =====
unsigned long lastSensorRead = 0;
unsigned long lastMqttReconnectAttempt = 0;

// ===== Connection State Tracking =====
bool wasMqttConnected = false;
bool wasWifiConnected = false;

// ===== Forward Declarations =====
void setupWiFi();
void setupMQTT();
void reconnectMQTT();
void publishSensorData();
void flushBuffer();

/**
 * @brief Setup function - runs once at startup
 */
void setup() {
    // Initialize Serial
    Serial.begin(115200);
    delay(100);
    Serial.println("\n\n=== ESP32 IoT Sensor Device ===");
    Serial.println("Starting initialization...\n");
    
    // Setup WiFi
    setupWiFi();
    
    // Setup MQTT
    setupMQTT();
    
    // Register sensors with manager
    Serial.println("[Main] Registering sensors...");
    sensorManager.addSensor(new DHT22Sensor(DHT22_PIN));
    sensorManager.addSensor(new FlameSensor(FLAME_DIGITAL_PIN, FLAME_ANALOG_PIN));
    
    // Initialize all sensors
    if (!sensorManager.initAll()) {
        Serial.println("[Main] Warning: Not all sensors initialized successfully");
    }
    
    Serial.println("[Main] Setup complete! Starting main loop.\n");
}

/**
 * @brief Main loop - runs continuously
 */
void loop() {
    // ----- WiFi state transitions -----
    bool wifiUp = (WiFi.status() == WL_CONNECTED);
    if (!wifiUp && wasWifiConnected) {
        Serial.println("\n[WiFi] *** CONNECTION LOST ***");
    }
    wasWifiConnected = wifiUp;

    if (!wifiUp) {
        Serial.println("[Main] WiFi disconnected, reconnecting...");
        setupWiFi();
    }

    // ----- MQTT state transitions -----
    // Check the underlying TCP socket directly — lwIP can detect a CLOSE_WAIT
    // / RST faster than PubSubClient's keepalive logic. If the socket is dead
    // but PubSubClient still thinks it's connected, force it to reconcile.
    if (mqttClient.connected() && !espClient.connected()) {
        Serial.println("\n[MQTT] TCP socket dead — forcing PubSubClient disconnect");
        mqttClient.disconnect();
    }

    bool mqttUp = mqttClient.connected();
    if (!mqttUp && wasMqttConnected) {
        Serial.printf("\n[MQTT] *** CONNECTION LOST *** (rc=%d) — readings will be buffered\n",
                      mqttClient.state());
    }
    wasMqttConnected = mqttUp;

    if (!mqttUp) {
        reconnectMQTT();
    }

    // Keep MQTT client alive (drives keepalive pings + detects drops)
    mqttClient.loop();

    // Read and publish sensor data at regular interval
    unsigned long now = millis();
    if (now - lastSensorRead >= SENSOR_READ_INTERVAL) {
        lastSensorRead = now;
        publishSensorData();
    }

    delay(100);  // Small delay to avoid watchdog timeout
}

/**
 * @brief Connect to WiFi network
 */
void setupWiFi() {
    Serial.printf("\n[WiFi] Connecting to %s", WIFI_SSID);
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(" SUCCESS");
        Serial.printf("[WiFi] IP address: %s\n", WiFi.localIP().toString().c_str());
        Serial.printf("[WiFi] RSSI: %d dBm\n", WiFi.RSSI());
    } else {
        Serial.println(" FAILED");
        Serial.println("[WiFi] Check SSID, password, and WiFi signal strength");
    }
}

/**
 * @brief Setup MQTT client
 */
void setupMQTT() {
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    // Short keepalive so a dropped connection is detected within ~MQTT_KEEPALIVE
    // seconds instead of the 15s default. Must be > publish interval / 1000.
    mqttClient.setKeepAlive(MQTT_KEEPALIVE);
    mqttClient.setSocketTimeout(MQTT_SOCKET_TIMEOUT);
    Serial.printf("[MQTT] Broker: %s:%d\n", MQTT_SERVER, MQTT_PORT);
    Serial.printf("[MQTT] Client ID: %s, keepalive: %ds\n", MQTT_CLIENT_ID, MQTT_KEEPALIVE);
}

/**
 * @brief Reconnect to MQTT broker with retry logic
 */
void reconnectMQTT() {
    unsigned long now = millis();
    
    // Only attempt reconnection at intervals to avoid flooding
    if (now - lastMqttReconnectAttempt < MQTT_RECONNECT_INTERVAL) {
        return;
    }
    
    lastMqttReconnectAttempt = now;
    
    if (!mqttClient.connected()) {
        Serial.print("[MQTT] Attempting connection... ");
        
        if (mqttClient.connect(MQTT_CLIENT_ID)) {
            Serial.println("CONNECTED");
            Serial.printf("[MQTT] *** CONNECTION RESTORED *** Topic: %s\n", MQTT_TOPIC_SENSORS);
            wasMqttConnected = true;
            flushBuffer();
        } else {
            Serial.printf("FAILED (rc=%d)\n", mqttClient.state());
            Serial.println("[MQTT] Will retry in 5 seconds");
        }
    }
}

/**
 * @brief Read all sensors and publish data to MQTT.
 * On publish failure the payload is pushed to the offline buffer so it
 * can be replayed (in order, with original timestamps) once reconnected.
 */
void publishSensorData() {
    JsonDocument jsonDoc;

    if (!sensorManager.readAll(jsonDoc)) {
        Serial.println("[Publish] Warning: Some sensor reads failed");
    }

    char jsonBuffer[PAYLOAD_MAX_LEN];
    unsigned long capturedAt = jsonDoc["timestamp"].as<unsigned long>();
    size_t jsonSize = serializeJson(jsonDoc, jsonBuffer);

    // Skip publish entirely if we know the link is down — publish() would
    // otherwise return true while writing to a dead socket buffer, falsely
    // reporting success. Three-layer check: WiFi link, TCP socket, MQTT state.
    if (WiFi.status() != WL_CONNECTED || !espClient.connected() || !mqttClient.connected()) {
        Serial.println("[Publish] OFFLINE - buffering reading for later replay");
        messageBuffer.push(jsonBuffer, capturedAt);
        return;
    }

    if (mqttClient.publish(MQTT_TOPIC_SENSORS, jsonBuffer)) {
        Serial.printf("[Publish] SUCCESS - %zu bytes sent\n", jsonSize);
        Serial.printf("  Topic: %s\n", MQTT_TOPIC_SENSORS);
        Serial.printf("  Payload: %s\n", jsonBuffer);
    } else {
        Serial.printf("[Publish] FAILED (rc=%d) - buffering reading for later replay\n",
                      mqttClient.state());
        messageBuffer.push(jsonBuffer, capturedAt);
    }
}

/**
 * @brief Drain the offline buffer, replaying stored readings in FIFO order.
 * Called immediately after a successful MQTT reconnection.
 */
void flushBuffer() {
    if (messageBuffer.isEmpty()) return;

    Serial.printf("[Buffer] Flushing %d buffered reading(s)...\n", messageBuffer.count());

    BufferedMessage msg;
    int flushed = 0;
    while (messageBuffer.pop(msg)) {
        if (mqttClient.publish(MQTT_TOPIC_SENSORS, msg.payload)) {
            flushed++;
            Serial.printf("[Buffer] Replayed reading t=%lums (%d left)\n",
                          msg.capturedAt, messageBuffer.count());
        } else {
            // Broker refused mid-flush — push back and stop
            messageBuffer.push(msg.payload, msg.capturedAt);
            Serial.printf("[Buffer] Publish failed mid-flush, %d reading(s) re-queued\n",
                          messageBuffer.count());
            break;
        }
        mqttClient.loop();  // keep connection alive between publishes
    }

    Serial.printf("[Buffer] Flush complete — %d sent, %d remaining\n",
                  flushed, messageBuffer.count());
}
