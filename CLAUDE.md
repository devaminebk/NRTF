# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Layout

This is the **Re·Tech Fusion hackathon** repo (INSAT, University of Carthage). The PlatformIO project lives in `part1/` — not at the repo root. Additional `partN/` folders may be added later.

Open `NRTF.code-workspace` (multi-root workspace) so PlatformIO detects `part1/` as a project. Opening just the `NRTF/` folder breaks IntelliSense include paths and lib resolution.

## Build / Upload / Monitor

All commands run from `part1/`:

```bash
pio run                    # compile
pio run --target upload    # flash to ESP32 (port set in platformio.ini, currently COM5)
pio device monitor         # serial monitor at 115200
```

Target board: `esp32doit-devkit-v1`. No test framework is configured.

## Architecture

The firmware uses a **plugin-style sensor architecture** so new sensors can be added without modifying existing files:

- `SensorBase` (abstract) — defines `init()`, `read(JsonObject&)`, `getName()`
- Concrete sensors (`DHT22Sensor`, `FlameSensor`) inherit and implement the interface
- `SensorManager` holds a `std::vector<SensorBase*>`, calls `readAll()` which writes each sensor's data into a nested JSON object keyed by `getName()`
- `main.cpp` registers sensors in `setup()` via `sensorManager.addSensor(new XxxSensor(pin))`, then the loop publishes the aggregated JSON to MQTT topic `esp32/sensors` every `SENSOR_READ_INTERVAL` ms

To add a sensor: create header+impl under `include/sensors/` and `src/sensors/`, inherit `SensorBase`, register it in `setup()`. Nothing else changes — JSON output picks it up automatically.

All hardcoded config (WiFi creds, MQTT broker IP, pin assignments, intervals, validation ranges) lives in `include/config.h`.

## Library / API Notes

- `platformio.ini` pins `ArduinoJson@7.0.4`. **Do not use `StaticJsonDocument<N>` or `DynamicJsonDocument` — those were removed in v7.** Use plain `JsonDocument` (no template parameter, no size).
- MQTT uses `PubSubClient` (synchronous) — fine for the 5s publish cadence.
- The loop has a 100ms `delay()` to feed the watchdog; don't remove it without replacing with `yield()` or similar.

## Conventions

- Serial logs use `[ComponentName]` prefix (e.g. `[WiFi]`, `[MQTT]`, `[Main]`, `[Publish]`)
- camelCase variables, PascalCase classes
- Sensor `read()` implementations should validate (NaN check, range check) and return `false` on bad data
