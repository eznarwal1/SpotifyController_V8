#include "Controls.h"

void Controls::sendPlayPause()
{
    Serial.println("{\"type\":\"command\",\"command\":\"play_pause\"}");
}

void Controls::sendPrevious()
{
    Serial.println("{\"type\":\"command\",\"command\":\"previous\"}");
}

void Controls::sendNext()
{
    Serial.println("{\"type\":\"command\",\"command\":\"next\"}");
}

void Controls::sendShuffle()
{
    Serial.println("{\"type\":\"command\",\"command\":\"shuffle\"}");
}

void Controls::sendRepeat()
{
    Serial.println("{\"type\":\"command\",\"command\":\"repeat\"}");
}

void Controls::sendVolume(int8_t amount)
{
    Serial.printf(
        "{\"type\":\"command\",\"command\":\"volume\",\"amount\":%d}\n",
        amount
    );
}

void Controls::sendMute()
{
    Serial.println("{\"type\":\"command\",\"command\":\"mute\"}");
}
