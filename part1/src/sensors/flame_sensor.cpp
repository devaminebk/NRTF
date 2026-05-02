#include "../include/sensors/flame_sensor.h"
#include "../include/config.h"

FlameSensor::FlameSensor(int dPin, int aPin)
    : digitalPin(dPin), analogPin(aPin), lastDigital(0), lastAnalog(0) {
}

FlameSensor::~FlameSensor() {
}

bool FlameSensor::init() {
    Serial.println("[FlameSensor] Initializing...");
    pinMode(digitalPin, INPUT);
    // analogPin is already configured by ADC, no setup needed
    delay(100);
    Serial.println("[FlameSensor] Initialization successful");
    return true;
}

bool FlameSensor::read(JsonObject& jsonDoc) {
    // Read digital output (1 = flame detected, 0 = no flame)
    int digital = digitalRead(digitalPin);
    
    // Read analog output (0-4095)
    int analog = analogRead(analogPin);
    
    // Validate analog data
    if (analog < FLAME_ANALOG_MIN || analog > FLAME_ANALOG_MAX) {
        Serial.printf("[FlameSensor] Error: Analog value out of range: %d\n", analog);
        return false;
    }
    
    lastDigital = digital;
    lastAnalog = analog;
    
    jsonDoc["flame_digital"] = digital;
    jsonDoc["flame_analog"] = analog;
    
    return true;
}
