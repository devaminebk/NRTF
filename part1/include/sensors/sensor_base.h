#ifndef SENSOR_BASE_H
#define SENSOR_BASE_H

#include <ArduinoJson.h>

/**
 * @class SensorBase
 * @brief Abstract base class for all sensors
 * 
 * All sensor implementations must inherit from this class and implement:
 * - init(): Initialize sensor (I2C, pins, etc.)
 * - read(): Read sensor data and populate JSON object
 */
class SensorBase {
public:
    virtual ~SensorBase() {}
    
    /**
     * @brief Initialize the sensor
     * @return true if initialization successful, false otherwise
     */
    virtual bool init() = 0;
    
    /**
     * @brief Read sensor data and add to JSON object
     * @param jsonDoc Reference to JsonObject to populate with sensor data
     * @return true if read was successful, false otherwise
     */
    virtual bool read(JsonObject& jsonDoc) = 0;
    
    /**
     * @brief Get sensor name (for debugging/logging)
     * @return Sensor name string
     */
    virtual const char* getName() const = 0;
};

#endif
