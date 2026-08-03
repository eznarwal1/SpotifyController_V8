#include "DisplayManager.h"

#include "pins_config.h"
#include "LovyanGFX_Driver.h"

#include <Wire.h>
#include <esp_heap_caps.h>

extern LGFX gfx;

static void sendI2CCommand(uint8_t command)
{
    Wire.beginTransmission(0x30);
    Wire.write(command);
    Wire.endTransmission();
}

void DisplayManager::flush(
    lv_disp_drv_t* display,
    const lv_area_t* area,
    lv_color_t* colors
)
{
    const uint32_t width = area->x2 - area->x1 + 1;
    const uint32_t height = area->y2 - area->y1 + 1;

    gfx.pushImage(
        area->x1,
        area->y1,
        width,
        height,
        reinterpret_cast<lgfx::rgb565_t*>(&colors->full)
    );

    lv_disp_flush_ready(display);
}

void DisplayManager::readTouch(
    lv_indev_drv_t* input,
    lv_indev_data_t* data
)
{
    (void)input;

    uint16_t x = 0;
    uint16_t y = 0;

    if (!gfx.getTouch(&x, &y) ||
        x >= LCD_H_RES ||
        y >= LCD_V_RES)
    {
        data->state = LV_INDEV_STATE_REL;
        return;
    }

    data->state = LV_INDEV_STATE_PR;
    data->point.x = x;
    data->point.y = y;
}

bool DisplayManager::begin()
{
    pinMode(19, OUTPUT);

    gfx.init();
    gfx.fillScreen(TFT_BLACK);
    delay(100);

    sendI2CCommand(0x10);
    delay(100);

    lv_init();

    constexpr uint32_t BUFFER_LINES = 20;
    const size_t bufferSize =
        sizeof(lv_color_t) * LCD_H_RES * BUFFER_LINES;

    drawBuffer_ = static_cast<lv_color_t*>(
        heap_caps_malloc(
            bufferSize,
            MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT
        )
    );

    if (drawBuffer_ == nullptr)
    {
        return false;
    }

    lv_disp_draw_buf_init(
        &drawBufferDescriptor_,
        drawBuffer_,
        nullptr,
        LCD_H_RES * BUFFER_LINES
    );

    static lv_disp_drv_t displayDriver;
    lv_disp_drv_init(&displayDriver);
    displayDriver.hor_res = LCD_H_RES;
    displayDriver.ver_res = LCD_V_RES;
    displayDriver.flush_cb = flush;
    displayDriver.draw_buf = &drawBufferDescriptor_;
    displayDriver.full_refresh = 0;
    displayDriver.direct_mode = 0;
    lv_disp_drv_register(&displayDriver);

    static lv_indev_drv_t inputDriver;
    lv_indev_drv_init(&inputDriver);
    inputDriver.type = LV_INDEV_TYPE_POINTER;
    inputDriver.read_cb = readTouch;
    lv_indev_drv_register(&inputDriver);

    gfx.fillScreen(TFT_BLACK);
    return true;
}

void DisplayManager::update()
{
    lv_timer_handler();
}
