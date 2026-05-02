#ifndef FLAME_SENSOR_H
#define FLAME_SENSOR_H

#include "sensor_base.h"

/**
 * @class FlameSensor
 * @brief Flame sensor implementation (digital + analog)
 * 
 * Reads both:
 * - flame_digital: 1 if flame detected, 0 if not
 * - flame_analog: Raw ADC value (0-4095)
 */
class FlameSensor : public SensorBase {
private:
    int digitalPin;
    int analogPin;
    int lastDigital;
    int lastAnalog;

public:
    FlameSensor(int dPin, int aPin);
    ~FlameSensor();
    
    bool init() override;
    bool read(JsonObject& jsonDoc) override;
    const char* getName() const override { return "FlameSensor"; }
};

#endif
