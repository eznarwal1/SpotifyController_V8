#include "SourceImage.h"

#include <esp_heap_caps.h>
#include <cstring>

SourceImage::SourceImage()
    : imageObject_(nullptr),
      frontBuffer_(nullptr),
      receiveBuffer_(nullptr)
{
    memset(&descriptor_, 0, sizeof(descriptor_));
}

SourceImage::~SourceImage()
{
    cancel();

    if (frontBuffer_ != nullptr)
    {
        heap_caps_free(frontBuffer_);
        frontBuffer_ = nullptr;
    }
}

void SourceImage::attach(lv_obj_t* imageObject)
{
    imageObject_ = imageObject;
}

bool SourceImage::beginReceive(
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

uint8_t* SourceImage::receiveBuffer()
{
    return receiveBuffer_;
}

void SourceImage::commit()
{
    if (receiveBuffer_ == nullptr || imageObject_ == nullptr)
    {
        return;
    }

    if (frontBuffer_ != nullptr)
    {
        heap_caps_free(frontBuffer_);
    }

    frontBuffer_ = receiveBuffer_;
    receiveBuffer_ = nullptr;

    memset(&descriptor_, 0, sizeof(descriptor_));
    descriptor_.header.always_zero = 0;
    descriptor_.header.w = WIDTH;
    descriptor_.header.h = HEIGHT;
    descriptor_.header.cf = LV_IMG_CF_TRUE_COLOR;
    descriptor_.data_size = BYTE_COUNT;
    descriptor_.data = frontBuffer_;

    lv_img_set_src(imageObject_, &descriptor_);
    lv_obj_clear_flag(imageObject_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_invalidate(imageObject_);
}

void SourceImage::cancel()
{
    if (receiveBuffer_ != nullptr)
    {
        heap_caps_free(receiveBuffer_);
        receiveBuffer_ = nullptr;
    }
}
