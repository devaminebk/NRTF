# ESP32 IoT Sensor Device - Re·Tech Fusion Hackathon Part 1

A modular, extensible PlatformIO project for the ESP32 WROOM-32D that reads sensor data and publishes it via MQTT to enable IoT data pipelines. Designed for the Re·Tech Fusion hackathon with scoring rubric alignment.

## Features

- **Multi-Sensor Support**: DHT22 (temperature/humidity) + Flame sensor (digital/analog) with easy addition of more sensors
- **MQTT Transport**: Publishes sensor data as JSON to a configurable Mosquitto broker
- **Modular Architecture**: Sensor base class + concrete implementations; manager handles aggregation
- **Data Validation**: Range checking, NaN detection, null prevention
- **Reconnection Handling**: MQTT reconnection with 5-second retry intervals
- **Simultaneous Sensor Reading**: All sensors read in single loop cycle
- **Extensible Design**: New sensors require only new class file + registration, no changes to existing code

## Project Structure

```
part1/
├── platformio.ini           # PlatformIO configuration
├── README.md                # This file
├── src/
│   ├── main.cpp             # Main app (WiFi, MQTT, loop)
│   ├── sensor_manager.cpp   # Sensor aggregation
│   └── sensors/
│       ├── dht22_sensor.cpp      # DHT22 implementation
│       └── flame_sensor.cpp      # Flame sensor implementation
├── include/
│   ├── config.h             # Configuration constants
│   ├── sensor_manager.h     # Sensor manager header
│   └── sensors/
│       ├── sensor_base.h    # Abstract sensor base
│       ├── dht22_sensor.h   # DHT22 header
│       └── flame_sensor.h   # Flame sensor header
└── .github/
    └── copilot-instructions.md
```

## Configuration

Edit `include/config.h` to customize:

```cpp
#define WIFI_SSID "Galaxy S20 Fe"
#define WIFI_PASSWORD "s20fe2004"
#define MQTT_SERVER "192.168.1.100"  // Update to your PC's IP
#define MQTT_PORT 1883

#define DHT22_PIN 4
#define FLAME_DIGITAL_PIN 5
#define FLAME_ANALOG_PIN 34

#define SENSOR_READ_INTERVAL 5000  // 5 seconds
```

## Hardware Wiring

| Component      | ESP32 Pin | Notes               |
|---|---|---|
| DHT22 Data     | GPIO 4    | 10k pullup resistor |
| Flame Digital  | GPIO 5    | Digital output      |
| Flame Analog   | GPIO 34   | ADC (32-bit ADC1)   |
| GND            | GND       | Common ground       |
| 5V/3.3V        | 5V/3.3V   | Per sensor specs    |

## MQTT Data Format

Published to topic `esp32/sensors`:

```json
{
  "timestamp": 12345678,
  "sensors": {
    "DHT22": {
      "temperature": 25.5,
      "humidity": 60.2
    },
    "FlameSensor": {
      "flame_digital": 0,
      "flame_analog": 1024
    }
  }
}
```

## Building & Uploading

### Prerequisites

- [PlatformIO](https://platformio.org/) installed in VS Code
- ESP32 board connected via USB (update `COM` port in `platformio.ini`)
- Mosquitto MQTT broker running on local PC

### Build

```bash
pio run
```

### Upload

```bash
pio run --target upload
```

### Monitor Serial Output

```bash
pio device monitor
```

## Verification Checklist

- [ ] Project compiles without errors
- [ ] ESP32 connects to WiFi (check serial output for IP)
- [ ] MQTT connects to broker (check "CONNECTED" message)
- [ ] Sensor data published every 5 seconds
- [ ] JSON valid and all fields present
- [ ] Mosquitto receives messages: `mosquitto_sub -h 192.168.1.100 -t esp32/sensors`
- [ ] Simulate MQTT disconnection → reconnects within 5 seconds
- [ ] Temperature/humidity in valid ranges
- [ ] Flame readings correct (digital 0/1, analog 0-4095)

## Adding New Sensors

1. Create header `include/sensors/YOUR_SENSOR.h`
2. Create implementation `src/sensors/YOUR_SENSOR.cpp`
3. Inherit from `SensorBase`, implement `init()`, `read()`, `getName()`
4. In `src/main.cpp`, add to setup:
   ```cpp
   sensorManager.addSensor(new YourSensor(pin));
   ```
5. No changes needed to existing sensor files

## Scoring Rubric Alignment

| Criterion | Implementation |
|---|---|
| Solution delivered & functional (30 pts) | MQTT publishes valid JSON with sensor data |
| Multi-sensor coordination (25 pts) | DHT22 + Flame read simultaneously every 5s |
| Protocol design & security (15 pts) | MQTT with reconnection logic, future TLS support |
| Uptime & continuity (15 pts) | 5-min window tracking via timestamp, reconnection |
| Data quality (10 pts) | Range validation, no nulls, no -999 sentinels |
| Innovation bonus (15 pts) | Modular sensor arch, extensible for future sensors, OTA/buffering framework ready |

## Troubleshooting

**ESP32 not connecting to WiFi:**
- Check SSID/password in `config.h`
- Verify WiFi 2.4GHz (not 5GHz)
- Check antenna connection on ESP32

**MQTT connection fails (rc=-2):**
- Verify Mosquitto running: `mosquitto -v` or `mosquitto_broker start`
- Check broker IP in `config.h` (use `ipconfig` on Windows to find PC IP)
- Test broker locally: `mosquitto_pub -h localhost -t test -m "hello"`

**Sensor reads invalid (NaN):**
- Verify wiring, especially data pin for DHT22
- Check power supply (3.3V for DHT22, proper voltage for flame sensor)
- Increase DHT22_PIN delay in initialization

## Future Enhancements

- OTA firmware updates
- Device-side buffering (SD card or flash storage)
- TLS/HTTPS with certificate support
- Additional sensors: MQ-series, INA219, BMP280, MPU6050, ultrasonic, CO₂ NDIR
- HTTP fallback transport
- Edge ML inference integration

## License

Part of Re·Tech Fusion hackathon. INSAT, University of Carthage.
