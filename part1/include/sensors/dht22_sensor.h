#ifndef DHT22_SENSOR_H
#define DHT22_SENSOR_H

#include "sensor_base.h"
#include <DHT.h>

/**
 * @class DHT22Sensor
 * @brief DHT22 temperature and humidity sensor implementation
 * 
 * Reads temperature (Celsius) and humidity (%)
 * from DHT22 sensor connected to specified pin.
 */
class DHT22Sensor : public SensorBase {
private:
    DHT dht;
    int pin;
    float lastTemperature;
    float lastHumidity;

public:
    DHT22Sensor(int dhtPin);
    ~DHT22Sensor();
    
    bool init() override;
    bool read(JsonObject& jsonDoc) override;
    const char* getName() const override { return "DHT22"; }
};

#endif
