#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

#include "SpotifyUI.h"
#include "Artwork.h"
#include "MetadataImage.h"
#include "SourceImage.h"
#include "ViewImage.h"
#include "BackgroundImage.h"

class Protocol
{
public:
    Protocol(
        SpotifyUI& ui,
        Artwork& artwork,
        MetadataImage& metadataImage,
        SourceImage& sourceImage,
        ViewImage& viewImage,
        BackgroundImage& backgroundImage
    );

    void poll();

private:
    enum class Mode
    {
        Json,
        BinaryHeader,
        BinaryPayload
    };

    enum class BinaryTarget
    {
        None,
        Artwork,
        Metadata,
        Source,
        View,
        Background
    };

    static constexpr uint8_t MAGIC[4] = {'S', 'P', 'V', '2'};
    static constexpr uint8_t VERSION = 2;
    static constexpr uint8_t TYPE_ARTWORK_RGB565 = 1;
    static constexpr uint8_t TYPE_METADATA_RGB565 = 2;
    static constexpr uint8_t TYPE_SOURCE_RGB565 = 3;
    static constexpr uint8_t TYPE_VIEW_RGB565 = 4;
    static constexpr uint8_t TYPE_BACKGROUND_RGB565 = 5;
    static constexpr size_t HEADER_SIZE = 18;

    SpotifyUI& ui_;
    Artwork& artwork_;
    MetadataImage& metadataImage_;
    SourceImage& sourceImage_;
    ViewImage& viewImage_;
    BackgroundImage& backgroundImage_;

    Mode mode_;
    BinaryTarget target_;
    String jsonLine_;
    uint8_t header_[HEADER_SIZE];
    size_t headerReceived_;
    uint32_t payloadLength_;
    uint32_t payloadReceived_;
    uint32_t expectedCrc_;
    uint32_t runningCrc_;
    uint16_t width_;
    uint16_t height_;

    void resetBinary();
    bool validateHeader();
    void processJsonLine();
    void finishPacket();
    uint8_t* targetBuffer();
    void cancelTarget();

    static uint16_t readLe16(const uint8_t* data);
    static uint32_t readLe32(const uint8_t* data);
    static uint32_t crc32Update(
        uint32_t crc,
        const uint8_t* data,
        size_t length
    );
};
