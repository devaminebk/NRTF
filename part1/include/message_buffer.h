#ifndef MESSAGE_BUFFER_H
#define MESSAGE_BUFFER_H

#include <Arduino.h>
#include "config.h"

struct BufferedMessage {
    char    payload[PAYLOAD_MAX_LEN];
    unsigned long capturedAt;  // millis() when the reading was taken
};

// Fixed-size circular (ring) buffer. When full, the oldest entry is
// overwritten so recent data is always preserved.
class MessageBuffer {
public:
    MessageBuffer();

    // Push a serialized JSON payload. capturedAt is the millis() timestamp
    // from when the sensor was read (already embedded in the JSON, stored
    // here separately for logging during flush).
    void push(const char* payload, unsigned long capturedAt);

    // Pop the oldest entry into `out`. Returns false if empty.
    bool pop(BufferedMessage& out);

    bool isEmpty() const { return _count == 0; }
    bool isFull()  const { return _count >= BUFFER_MAX_SIZE; }
    int  count()   const { return _count; }

private:
    BufferedMessage _buf[BUFFER_MAX_SIZE];
    int _head  = 0;   // next write slot
    int _tail  = 0;   // next read slot
    int _count = 0;
};

#endif
