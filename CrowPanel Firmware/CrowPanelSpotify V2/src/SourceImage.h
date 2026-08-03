#pragma once

#include <Arduino.h>
#include <lvgl.h>

class SourceImage
{
public:
    static constexpr uint16_t WIDTH = 220;
    static constexpr uint16_t HEIGHT = 38;
    static constexpr size_t BYTE_COUNT =
        static_cast<size_t>(WIDTH) * HEIGHT * 2U;

    SourceImage();
    ~SourceImage();

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
