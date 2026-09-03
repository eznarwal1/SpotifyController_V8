#include "ViewImage.h"

#include <esp_heap_caps.h>
#include <cstring>

ViewImage::ViewImage()
    : imageObject_(nullptr),
      frontBuffer_(nullptr),
      pendingBuffer_(nullptr),
      receiveBuffer_(nullptr)
{
    memset(&descriptor_, 0, sizeof(descriptor_));
}

ViewImage::~ViewImage()
{
    cancel();
    if (frontBuffer_ != nullptr)
    {
        heap_caps_free(frontBuffer_);
    }

    if (pendingBuffer_ != nullptr)
    {
        heap_caps_free(pendingBuffer_);
    }
}

void ViewImage::attach(lv_obj_t* imageObject)
{
    imageObject_ = imageObject;
}

bool ViewImage::beginReceive(
    uint16_t width,
    uint16_t height,
    uint32_t length
)
{
    cancel();

    if (width != WIDTH || height != HEIGHT || length != BYTE_COUNT)
    {
        return false;
    }

    receiveBuffer_ = static_cast<uint8_t*>(
        heap_caps_malloc(length, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT)
    );

    if (receiveBuffer_ == nullptr)
    {
        receiveBuffer_ = static_cast<uint8_t*>(
            heap_caps_malloc(length, MALLOC_CAP_INTERNAL | MALLOC_CAP_8BIT)
        );
    }

    return receiveBuffer_ != nullptr;
}

uint8_t* ViewImage::receiveBuffer()
{
    return receiveBuffer_;
}

void ViewImage::commit()
{
    if (receiveBuffer_ == nullptr)
    {
        return;
    }

    // Do not change the LVGL image source from inside serial packet handling.
    // Store the complete frame and apply it during the normal display loop.
    if (pendingBuffer_ != nullptr)
    {
        heap_caps_free(pendingBuffer_);
    }

    pendingBuffer_ = receiveBuffer_;
    receiveBuffer_ = nullptr;
}

bool ViewImage::applyPending()
{
    if (pendingBuffer_ == nullptr || imageObject_ == nullptr)
    {
        return false;
    }

    uint8_t* previousFront = frontBuffer_;
    frontBuffer_ = pendingBuffer_;
    pendingBuffer_ = nullptr;

    memset(&descriptor_, 0, sizeof(descriptor_));
    descriptor_.header.always_zero = 0;
    descriptor_.header.w = WIDTH;
    descriptor_.header.h = HEIGHT;
    descriptor_.header.cf = LV_IMG_CF_TRUE_COLOR;
    descriptor_.data_size = BYTE_COUNT;
    descriptor_.data = frontBuffer_;

    lv_img_set_src(imageObject_, &descriptor_);
    lv_obj_invalidate(imageObject_);

    // LVGL has accepted the new source. The previous buffer is no longer used
    // by this image descriptor and can now be released.
    if (previousFront != nullptr)
    {
        heap_caps_free(previousFront);
    }

    return true;
}

void ViewImage::cancel()
{
    if (receiveBuffer_ != nullptr)
    {
        heap_caps_free(receiveBuffer_);
        receiveBuffer_ = nullptr;
    }
}
