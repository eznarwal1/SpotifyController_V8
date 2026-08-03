#pragma once
#include <Arduino.h>

struct AppState
{
    bool spotifyConnected = false;
    String application = "Media";
    String title = "";
    String artist = "";
    String album = "";
    bool playing = false;
    uint32_t positionMs = 0;
    uint32_t durationMs = 0;
    bool shuffle = false;
    String repeat = "None";
    int volume = 0;
    bool muted = false;

    bool discordCallActive = false;
    bool discordMuted = false;
    bool discordDeafened = false;

    bool batteryPresent = false;
    uint8_t batteryPercent = 0;
    bool batteryCharging = false;
    String viewMode = "now_playing";
    String notificationText = "";
    static constexpr uint8_t MAX_QUEUE_ENTRIES = 8;
    String queueSource = "";
    String queueEntries[MAX_QUEUE_ENTRIES];
    uint8_t queueCount = 0;
    uint8_t queueSelectedIndex = 0;

    uint32_t receivedAtMs = 0;
};
