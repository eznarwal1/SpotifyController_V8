#pragma once

#include <Arduino.h>
#include <lvgl.h>

class MetadataImage
{
public:
    static constexpr uint16_t WIDTH = 470;
    static constexpr uint16_t HEIGHT = 118;
    static constexpr size_t BYTE_COUNT =
        static_cast<size_t>(WIDTH) * HEIGHT * 2U;

    MetadataImage();
    ~MetadataImage();

    void attach(lv_obj_t* imageObject);
    bool beginReceive(uint16_t width, uint16_t height, uint32_t length);
    uint8_t* receiveBuffer();
    void commit();
    void cancel();

private:
    lv_obj_t* imageObject_;
    uint8_t* frontBuffer_;
    uint8_t* receiveBuffer_;
    lv_img_dsc_t descriptor_;
};
