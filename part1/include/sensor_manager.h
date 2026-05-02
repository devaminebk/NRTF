#ifndef SENSOR_MANAGER_H
#define SENSOR_MANAGER_H

#include "sensors/sensor_base.h"
#include <ArduinoJson.h>
#include <vector>

/**
 * @class SensorManager
 * @brief Manages all active sensors
 * 
 * Coordinates sensor initialization, simultaneous reading,
 * data validation, and JSON aggregation.
 * 
 * Easy to extend: just add new sensor class and register it.
 */
class SensorManager {
private:
    std::vector<SensorBase*> sensors;
    JsonDocument sensorData;

public:
    SensorManager();
    ~SensorManager();
    
    /**
     * @brief Register a sensor with the manager
     * @param sensor Pointer to sensor object (manager takes ownership)
     */
    void addSensor(SensorBase* sensor);
    
    /**
     * @brief Initialize all registered sensors
     * @return true if all sensors initialized successfully
     */
    bool initAll();
    
    /**
     * @brief Read all sensors simultaneously
     * @param jsonDoc Reference to JsonDocument to populate with all sensor data
     * @return true if all reads successful, false if any failed
     */
    bool readAll(JsonDocument& jsonDoc);
    
    /**
     * @brief Get count of registered sensors
     * @return Number of sensors
     */
    int getSensorCount() const { return sensors.size(); }
};

#endif
