#include "Artwork.h"

#include <esp_heap_caps.h>
#include <cstring>

namespace
{
void setArtworkOpacity(void* object, int32_t value)
{
    lv_obj_set_style_img_opa(
        static_cast<lv_obj_t*>(object),
        static_cast<lv_opa_t>(value),
        LV_PART_MAIN
    );
}

void animateOpacity(
    lv_obj_t* object,
    lv_opa_t from,
    lv_opa_t to,
    uint32_t duration
)
{
    if (object == nullptr)
    {
        return;
    }

    lv_anim_del(object, setArtworkOpacity);

    lv_anim_t animation;
    lv_anim_init(&animation);
    lv_anim_set_var(&animation, object);
    lv_anim_set_exec_cb(&animation, setArtworkOpacity);
    lv_anim_set_values(&animation, from, to);
    lv_anim_set_time(&animation, duration);
    lv_anim_set_path_cb(&animation, lv_anim_path_ease_out);
    lv_anim_start(&animation);
}
}

Artwork::Artwork()
    : imageObject_(nullptr),
      placeholderLabel_(nullptr),
      frontBuffer_(nullptr),
      receiveBuffer_(nullptr)
{
    memset(&descriptor_, 0, sizeof(descriptor_));
}

Artwork::~Artwork()
{
    cancel();

    if (frontBuffer_ != nullptr)
    {
        heap_caps_free(frontBuffer_);
        frontBuffer_ = nullptr;
    }
}

void Artwork::attach(lv_obj_t* imageObject, lv_obj_t* placeholderLabel)
{
    imageObject_ = imageObject;
    placeholderLabel_ = placeholderLabel;
}

bool Artwork::beginReceive(
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

    if (receiveBuffer_ != nullptr &&
        imageObject_ != nullptr &&
        !lv_obj_has_flag(imageObject_, LV_OBJ_FLAG_HIDDEN))
    {
        animateOpacity(imageObject_, LV_OPA_COVER, LV_OPA_20, 180);
    }

    return receiveBuffer_ != nullptr;
}

uint8_t* Artwork::receiveBuffer()
{
    return receiveBuffer_;
}

void Artwork::commit()
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

    lv_anim_del(imageObject_, setArtworkOpacity);
    lv_img_set_src(imageObject_, &descriptor_);
    lv_obj_clear_flag(imageObject_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_center(imageObject_);

    if (placeholderLabel_ != nullptr)
    {
        lv_obj_add_flag(placeholderLabel_, LV_OBJ_FLAG_HIDDEN);
    }

    lv_obj_set_style_img_opa(
        imageObject_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    animateOpacity(imageObject_, LV_OPA_TRANSP, LV_OPA_COVER, 220);
    lv_obj_invalidate(imageObject_);
}

void Artwork::cancel()
{
    if (receiveBuffer_ != nullptr)
    {
        heap_caps_free(receiveBuffer_);
        receiveBuffer_ = nullptr;
    }

    if (imageObject_ != nullptr &&
        !lv_obj_has_flag(imageObject_, LV_OBJ_FLAG_HIDDEN))
    {
        animateOpacity(imageObject_, LV_OPA_20, LV_OPA_COVER, 120);
    }
}
