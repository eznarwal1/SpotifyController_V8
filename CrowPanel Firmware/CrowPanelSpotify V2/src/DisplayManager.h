#pragma once

#include <Arduino.h>
#include <lvgl.h>

class DisplayManager
{
public:
    bool begin();
    void update();

private:
    static void flush(
        lv_disp_drv_t* display,
        const lv_area_t* area,
        lv_color_t* colors
    );
    static void readTouch(
        lv_indev_drv_t* input,
        lv_indev_data_t* data
    );

    lv_color_t* drawBuffer_ = nullptr;
    lv_disp_draw_buf_t drawBufferDescriptor_;
};
