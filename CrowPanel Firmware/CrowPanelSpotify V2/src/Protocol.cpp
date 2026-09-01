#include "Protocol.h"

#include <cstring>

constexpr uint8_t Protocol::MAGIC[4];

Protocol::Protocol(
    SpotifyUI& ui,
    Artwork& artwork,
    MetadataImage& metadataImage,
    SourceImage& sourceImage,
    ViewImage& viewImage,
    BackgroundImage& backgroundImage
)
    : ui_(ui),
      artwork_(artwork),
      metadataImage_(metadataImage),
      sourceImage_(sourceImage),
      viewImage_(viewImage),
      backgroundImage_(backgroundImage),
      mode_(Mode::Json),
      target_(BinaryTarget::None),
      headerReceived_(0),
      payloadLength_(0),
      payloadReceived_(0),
      expectedCrc_(0),
      runningCrc_(0xFFFFFFFFU),
      width_(0),
      height_(0)
{
}

uint16_t Protocol::readLe16(const uint8_t* data)
{
    return static_cast<uint16_t>(data[0]) |
           (static_cast<uint16_t>(data[1]) << 8);
}

uint32_t Protocol::readLe32(const uint8_t* data)
{
    return static_cast<uint32_t>(data[0]) |
           (static_cast<uint32_t>(data[1]) << 8) |
           (static_cast<uint32_t>(data[2]) << 16) |
           (static_cast<uint32_t>(data[3]) << 24);
}

uint32_t Protocol::crc32Update(
    uint32_t crc,
    const uint8_t* data,
    size_t length
)
{
    for (size_t index = 0; index < length; ++index)
    {
        crc ^= data[index];

        for (uint8_t bit = 0; bit < 8; ++bit)
        {
            const uint32_t mask =
                static_cast<uint32_t>(
                    -(static_cast<int32_t>(crc & 1U))
                );
            crc = (crc >> 1) ^ (0xEDB88320U & mask);
        }
    }

    return crc;
}

void Protocol::resetBinary()
{
    mode_ = Mode::Json;
    target_ = BinaryTarget::None;
    headerReceived_ = 0;
    payloadLength_ = 0;
    payloadReceived_ = 0;
    expectedCrc_ = 0;
    runningCrc_ = 0xFFFFFFFFU;
    width_ = 0;
    height_ = 0;
}

bool Protocol::validateHeader()
{
    if (memcmp(header_, MAGIC, sizeof(MAGIC)) != 0 ||
        header_[4] != VERSION)
    {
        return false;
    }

    width_ = readLe16(header_ + 6);
    height_ = readLe16(header_ + 8);
    payloadLength_ = readLe32(header_ + 10);
    expectedCrc_ = readLe32(header_ + 14);

    if (header_[5] == TYPE_ARTWORK_RGB565)
    {
        target_ = BinaryTarget::Artwork;
        return artwork_.beginReceive(width_, height_, payloadLength_);
    }

    if (header_[5] == TYPE_METADATA_RGB565)
    {
        target_ = BinaryTarget::Metadata;
        return metadataImage_.beginReceive(
            width_,
            height_,
            payloadLength_
        );
    }

    if (header_[5] == TYPE_SOURCE_RGB565)
    {
        target_ = BinaryTarget::Source;
        return sourceImage_.beginReceive(
            width_,
            height_,
            payloadLength_
        );
    }

    if (header_[5] == TYPE_VIEW_RGB565)
    {
        target_ = BinaryTarget::View;
        return viewImage_.beginReceive(
            width_,
            height_,
            payloadLength_
        );
    }

    if (header_[5] == TYPE_BACKGROUND_RGB565)
    {
        target_ = BinaryTarget::Background;
        return backgroundImage_.beginReceive(
            width_,
            height_,
            payloadLength_
        );
    }

    return false;
}

uint8_t* Protocol::targetBuffer()
{
    if (target_ == BinaryTarget::Artwork)
    {
        return artwork_.receiveBuffer();
    }

    if (target_ == BinaryTarget::Metadata)
    {
        return metadataImage_.receiveBuffer();
    }

    if (target_ == BinaryTarget::Source)
    {
        return sourceImage_.receiveBuffer();
    }

    if (target_ == BinaryTarget::View)
    {
        return viewImage_.receiveBuffer();
    }

    if (target_ == BinaryTarget::Background)
    {
        return backgroundImage_.receiveBuffer();
    }

    return nullptr;
}

void Protocol::cancelTarget()
{
    if (target_ == BinaryTarget::Artwork)
    {
        artwork_.cancel();
    }
    else if (target_ == BinaryTarget::Metadata)
    {
        metadataImage_.cancel();
    }
    else if (target_ == BinaryTarget::Source)
    {
        sourceImage_.cancel();
    }
    else if (target_ == BinaryTarget::View)
    {
        viewImage_.cancel();
    }
    else if (target_ == BinaryTarget::Background)
    {
        backgroundImage_.cancel();
    }
}

void Protocol::processJsonLine()
{
    jsonLine_.trim();

    if (jsonLine_.isEmpty())
    {
        return;
    }

    JsonDocument document;
    const DeserializationError error =
        deserializeJson(document, jsonLine_);

    if (error)
    {
        return;
    }

    const char* type = document["type"] | "";

    if (strcmp(type, "state") != 0)
    {
        return;
    }

    AppState state;
    state.spotifyConnected = document["spotify_connected"] | false;
    state.application = static_cast<const char*>(
        document["application"] | "Media"
    );
    state.title = static_cast<const char*>(document["title"] | "");
    state.artist = static_cast<const char*>(document["artist"] | "");
    state.album = static_cast<const char*>(document["album"] | "");
    state.playing = document["playing"] | false;
    state.positionMs = document["position_ms"] | 0U;
    state.durationMs = document["duration_ms"] | 0U;
    state.shuffle = document["shuffle"] | false;
    state.repeat = static_cast<const char*>(document["repeat"] | "None");
    state.volume = document["volume"] | 0;
    state.muted = document["muted"] | false;
    state.discordCallActive =
        document["discord_call_active"] | false;
    state.discordMuted = document["discord_muted"] | false;
    state.discordDeafened =
        document["discord_deafened"] | false;
    state.batteryPresent = document["battery_present"] | false;
    state.batteryPercent = document["battery_percent"] | 0;
    state.batteryCharging =
        document["battery_charging"] | false;
    state.viewMode = static_cast<const char*>(
        document["view_mode"] | "now_playing"
    );
    state.queueSource = static_cast<const char*>(
        document["queue_source"] | ""
    );
    state.queueCount = 0;

    JsonArray queueEntries =
        document["queue_entries"].as<JsonArray>();

    for (JsonVariant entry : queueEntries)
    {
        if (
            state.queueCount >=
            AppState::MAX_QUEUE_ENTRIES
        )
        {
            break;
        }

        state.queueEntries[state.queueCount] =
            static_cast<const char*>(entry | "");
        ++state.queueCount;
    }

    const int selectedQueueIndex =
        document["queue_selected_index"] | 0;

    if (state.queueCount == 0)
    {
        state.queueSelectedIndex = 0;
    }
    else
    {
        state.queueSelectedIndex = static_cast<uint8_t>(
            constrain(
                selectedQueueIndex,
                0,
                static_cast<int>(state.queueCount) - 1
            )
        );
    }
    state.mixerCount = 0;

    JsonArray mixerEntries =
        document["mixer_entries"].as<JsonArray>();
    JsonArray mixerVolumes =
        document["mixer_volumes"].as<JsonArray>();
    JsonArray mixerMuted =
        document["mixer_muted"].as<JsonArray>();

    for (JsonVariant entry : mixerEntries)
    {
        if (
            state.mixerCount >=
            AppState::MAX_MIXER_ENTRIES
        )
        {
            break;
        }

        state.mixerEntries[state.mixerCount] =
            static_cast<const char*>(entry | "");

        const uint8_t index = state.mixerCount;
        state.mixerVolumes[index] = static_cast<uint8_t>(
            constrain(
                mixerVolumes[index] | 0,
                0,
                100
            )
        );
        state.mixerMuted[index] =
            mixerMuted[index] | false;

        ++state.mixerCount;
    }

    const int selectedMixerIndex =
        document["mixer_selected_index"] | 0;

    if (state.mixerCount == 0)
    {
        state.mixerSelectedIndex = 0;
    }
    else
    {
        state.mixerSelectedIndex = static_cast<uint8_t>(
            constrain(
                selectedMixerIndex,
                0,
                static_cast<int>(state.mixerCount) - 1
            )
        );
    }
    state.receivedAtMs = millis();

    ui_.applyState(state);
}

void Protocol::finishPacket()
{
    const uint32_t actualCrc = runningCrc_ ^ 0xFFFFFFFFU;

    if (actualCrc == expectedCrc_)
    {
        if (target_ == BinaryTarget::Artwork)
        {
            artwork_.commit();
        }
        else if (target_ == BinaryTarget::Metadata)
        {
            metadataImage_.commit();
        }
        else if (target_ == BinaryTarget::Source)
        {
            sourceImage_.commit();
        }
        else if (target_ == BinaryTarget::View)
        {
            viewImage_.commit();
        }
        else if (target_ == BinaryTarget::Background)
        {
            backgroundImage_.commit();
        }

        Serial.println("{\"type\":\"ack\",\"packet\":\"binary\"}");
    }
    else
    {
        cancelTarget();
        Serial.println(
            "{\"type\":\"error\",\"packet\":\"binary\",\"reason\":\"crc\"}"
        );
    }

    resetBinary();
}

void Protocol::poll()
{
    constexpr size_t MAX_BYTES_PER_POLL = 32768;
    size_t processed = 0;

    while (Serial.available() > 0 && processed < MAX_BYTES_PER_POLL)
    {
        if (mode_ == Mode::BinaryPayload)
        {
            const size_t remaining = payloadLength_ - payloadReceived_;
            const size_t available =
                static_cast<size_t>(Serial.available());
            const size_t allowance = MAX_BYTES_PER_POLL - processed;
            const size_t request =
                min(remaining, min(available, allowance));

            if (request == 0)
            {
                break;
            }

            uint8_t* buffer = targetBuffer();

            if (buffer == nullptr)
            {
                cancelTarget();
                resetBinary();
                break;
            }

            uint8_t* destination = buffer + payloadReceived_;
            const size_t received = Serial.readBytes(
                reinterpret_cast<char*>(destination),
                request
            );

            if (received == 0)
            {
                break;
            }

            runningCrc_ = crc32Update(
                runningCrc_,
                destination,
                received
            );
            payloadReceived_ += received;
            processed += received;

            if (payloadReceived_ == payloadLength_)
            {
                finishPacket();
            }

            continue;
        }

        const int rawValue = Serial.read();

        if (rawValue < 0)
        {
            break;
        }

        const uint8_t value = static_cast<uint8_t>(rawValue);
        ++processed;

        if (mode_ == Mode::BinaryHeader)
        {
            header_[headerReceived_++] = value;

            if (headerReceived_ == HEADER_SIZE)
            {
                if (validateHeader())
                {
                    mode_ = Mode::BinaryPayload;
                    payloadReceived_ = 0;
                    runningCrc_ = 0xFFFFFFFFU;
                }
                else
                {
                    cancelTarget();
                    resetBinary();
                }
            }

            continue;
        }

        if (jsonLine_.isEmpty() && value == MAGIC[0])
        {
            mode_ = Mode::BinaryHeader;
            header_[0] = value;
            headerReceived_ = 1;
            continue;
        }

        const char character = static_cast<char>(value);

        if (character == '\n')
        {
            processJsonLine();
            jsonLine_ = "";
        }
        else if (character != '\r')
        {
            jsonLine_ += character;

            if (jsonLine_.length() > 1800)
            {
                jsonLine_ = "";
            }
        }
    }
}
