#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "config.h"
#include "sensor_manager.h"
#include "sensors/dht22_sensor.h"
#include "sensors/flame_sensor.h"

// ===== Global Objects =====
WiFiClient espClient;
PubSubClient mqttClient(espClient);
SensorManager sensorManager;

// ===== Timing Variables =====
unsigned long lastSensorRead = 0;
unsigned long lastMqttReconnectAttempt = 0;

// ===== Forward Declarations =====
void setupWiFi();
void setupMQTT();
void reconnectMQTT();
void publishSensorData();

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
    // Ensure WiFi is connected
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[Main] WiFi disconnected, reconnecting...");
        setupWiFi();
    }
    
    // Ensure MQTT is connected
    if (!mqttClient.connected()) {
        reconnectMQTT();
    }
    
    // Keep MQTT client alive
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
    Serial.printf("[MQTT] Broker: %s:%d\n", MQTT_SERVER, MQTT_PORT);
    Serial.printf("[MQTT] Client ID: %s\n", MQTT_CLIENT_ID);
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
            Serial.printf("[MQTT] Topic: %s\n", MQTT_TOPIC_SENSORS);
        } else {
            Serial.printf("FAILED (rc=%d)\n", mqttClient.state());
            Serial.println("[MQTT] Will retry in 5 seconds");
        }
    }
}

/**
 * @brief Read all sensors and publish data to MQTT
 */
void publishSensorData() {
    // Create JSON document
    StaticJsonDocument<512> jsonDoc;
    
    // Read all sensors simultaneously
    if (!sensorManager.readAll(jsonDoc)) {
        Serial.println("[Publish] Warning: Some sensor reads failed");
    }
    
    // Serialize JSON to string
    char jsonBuffer[512];
    size_t jsonSize = serializeJson(jsonDoc, jsonBuffer);
    
    // Publish to MQTT
    if (mqttClient.publish(MQTT_TOPIC_SENSORS, jsonBuffer)) {
        Serial.printf("[Publish] SUCCESS - %zu bytes sent\n", jsonSize);
        Serial.printf("  Topic: %s\n", MQTT_TOPIC_SENSORS);
        Serial.printf("  Payload: %s\n", jsonBuffer);
    } else {
        Serial.println("[Publish] FAILED - MQTT not connected or publish failed");
    }
}
