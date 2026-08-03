#pragma once

#include <Arduino.h>

class Controls
{
public:
    static void sendPlayPause();
    static void sendPrevious();
    static void sendNext();
    static void sendShuffle();
    static void sendRepeat();
    static void sendVolume(int8_t amount);
    static void sendMute();
};
