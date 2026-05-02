# Copilot Instructions for ESP32 IoT Sensor Device

## Project Overview

ESP32 WROOM-32D IoT device for Re·Tech Fusion hackathon Part 1. Reads DHT22 (temperature/humidity) and flame sensor (digital/analog), publishes via MQTT as JSON. Modular sensor architecture designed for easy addition of future sensors.

## Architecture & Code Patterns

### Sensor System

- **SensorBase** (`include/sensors/sensor_base.h`): Abstract interface with `init()`, `read()`, `getName()`
- **Concrete Sensors**: Each sensor (DHT22, FlameSensor) inherits SensorBase, implements interface
- **SensorManager** (`include/sensor_manager.h`): Aggregates sensors, handles simultaneous reading + JSON serialization
- **Pattern**: New sensors require only new class file + registration in `setup()`, NO changes to existing sensor files

### MQTT & WiFi

- **PubSubClient**: Synchronous MQTT library (sufficient for 5-second publish interval)
- **WiFi**: Automatic reconnection with retry logic
- **Reconnection**: 5-second intervals with logging for uptime tracking
- **Topic**: `esp32/sensors` → publishes JSON with timestamp + all sensor readings

### Data Flow

1. **Setup**: WiFi → MQTT client → register sensors → init all
2. **Loop**: 
   - Check WiFi/MQTT connection (reconnect if needed)
   - Every 5 seconds: read all sensors → validate data → JSON → publish
   - Small 100ms delay to prevent watchdog timeout

## Configuration

All hardcoded values in `include/config.h`:
- WiFi: SSID, password
- MQTT: broker IP (192.168.1.100), port, client ID, topic
- Sensors: pin assignments (DHT22=4, flame_digital=5, flame_analog=34)
- Timing: 5s read interval, 5s MQTT retry
- Validation ranges: temp -40 to 80°C, humidity 0-100%, flame_analog 0-4095

## Building & Testing

### Build
```
pio run                    # Compile
pio run --target upload    # Upload to ESP32
pio device monitor         # Watch serial output
```

### Verify
- Serial: "WiFi connected" → IP address, then "MQTT connected"
- Every 5s: "[Publish] SUCCESS" with JSON payload
- MQTT broker: `mosquitto_sub -h 192.168.1.100 -t esp32/sensors`

### Troubleshooting

**No WiFi**: Check SSID/password in config.h, verify 2.4GHz band
**No MQTT**: Verify Mosquitto running on PC, check broker IP with `ipconfig`
**Bad sensor reads**: Check wiring, power supply (3.3V), try reseating connectors

## Adding a New Sensor

1. Create `include/sensors/new_sensor.h` with class inheriting SensorBase
2. Create `src/sensors/new_sensor.cpp` with implementation
3. In `src/main.cpp` `setup()`, add: `sensorManager.addSensor(new NewSensor(pin));`
4. New sensor data automatically included in JSON output

Example:
```cpp
// new_sensor.h
class NewSensor : public SensorBase {
    bool init() override { /* init code */ return true; }
    bool read(JsonObject& json) override { 
        json["value"] = readValue();
        return true;
    }
    const char* getName() const override { return "NewSensor"; }
};
```

## Code Style & Conventions

- **Comments**: Use `[ComponentName]` prefix in Serial logs
- **Naming**: camelCase for variables, PascalCase for classes
- **Validation**: Always check for NaN (sensors) and range violations
- **Error Handling**: Return false on errors, log via Serial
- **Memory**: Use StaticJsonDocument (fixed size on stack), avoid dynamic allocation in loop

## Scoring Rubric Alignment

- **30pts (Solution)**: Validated JSON MQTT publish confirmed
- **25pts (Multi-sensor)**: DHT22 + FlameSensor read simultaneously
- **15pts (Protocol)**: MQTT with auto-reconnect + future TLS support
- **15pts (Uptime)**: Timestamp in JSON, reconnect tracking
- **10pts (Data quality)**: Range validation, no nulls, NaN detection
- **15pts (Innovation)**: Modular sensor arch (add sensors without code changes)

## Future Work

- OTA updates: Add firmware update over WiFi
- Buffering: Store readings in flash if MQTT fails
- TLS/HTTPS: Add certificate support for secure MQTT
- Additional sensors: MQ-series, INA219, BMP280, MPU6050, ultrasonic, CO₂
- HTTP fallback: Add WiFiClient publishing alternative
- Edge ML: Integrate inference on-device before publishing

## References

- [ESP32 Pinout](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/hw-reference/esp32_wroom_32_pinout.html)
- [DHT22 Datasheet](https://www.sparkfun.com/datasheets/Sensors/Temperature/DHT22.pdf)
- [PubSubClient](https://github.com/knolleary/pubsubclient)
- [ArduinoJson](https://arduinojson.org/)
- [Mosquitto](https://mosquitto.org/)
