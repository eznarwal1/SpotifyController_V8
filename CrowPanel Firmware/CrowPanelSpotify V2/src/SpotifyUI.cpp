#include "SpotifyUI.h"

SpotifyUI* SpotifyUI::instance_ = nullptr;

namespace
{
constexpr uint32_t BACKGROUND_COLOR = 0x121212;
constexpr uint32_t PANEL_COLOR = 0x282828;
constexpr uint32_t SECONDARY_TEXT_COLOR = 0xB3B3B3;
constexpr uint32_t INACTIVE_CONTROL_COLOR = 0xB3B3B3;
constexpr uint32_t PROGRESS_TRACK_COLOR = 0x535353;

constexpr lv_coord_t ARTWORK_SIZE = 210;
constexpr lv_coord_t ARTWORK_RADIUS = 10;

bool queueStateChanged(
    const AppState& previous,
    const AppState& current
)
{
    if (
        previous.queueSource != current.queueSource ||
        previous.queueCount != current.queueCount ||
        previous.queueSelectedIndex != current.queueSelectedIndex
    )
    {
        return true;
    }

    for (uint8_t index = 0; index < current.queueCount; ++index)
    {
        if (
            previous.queueEntries[index] !=
            current.queueEntries[index]
        )
        {
            return true;
        }
    }

    return false;
}

bool mixerStateChanged(
    const AppState& previous,
    const AppState& current
)
{
    if (
        previous.mixerCount != current.mixerCount ||
        previous.mixerSelectedIndex != current.mixerSelectedIndex
    )
    {
        return true;
    }

    for (uint8_t index = 0; index < current.mixerCount; ++index)
    {
        if (
            previous.mixerEntries[index] !=
                current.mixerEntries[index] ||
            previous.mixerVolumes[index] !=
                current.mixerVolumes[index] ||
            previous.mixerMuted[index] !=
                current.mixerMuted[index]
        )
        {
            return true;
        }
    }

    return false;
}

bool statusStateChanged(
    const AppState& previous,
    const AppState& current
)
{
    return (
        previous.discordCallActive != current.discordCallActive ||
        previous.discordMuted != current.discordMuted ||
        previous.discordDeafened != current.discordDeafened ||
        previous.batteryPresent != current.batteryPresent ||
        previous.batteryPercent != current.batteryPercent ||
        previous.batteryCharging != current.batteryCharging
    );
}
}

SpotifyUI::SpotifyUI()
    : title_(nullptr),
      artist_(nullptr),
      album_(nullptr),
      previousButton_(nullptr),
      playButton_(nullptr),
      playLabel_(nullptr),
      nextButton_(nullptr),
      progressBar_(nullptr),
      elapsed_(nullptr),
      duration_(nullptr),
      artworkContainer_(nullptr),
      artworkImage_(nullptr),
      artworkText_(nullptr),
      shuffleButton_(nullptr),
      shuffleLabel_(nullptr),
      repeatButton_(nullptr),
      repeatLabel_(nullptr),
      sourceButton_(nullptr),
      metadataImageObject_(nullptr),
      sourceLabel_(nullptr),
      sourceImageObject_(nullptr),
      voiceStatusDot_(nullptr),
      statusLabel_(nullptr),
      batteryLabel_(nullptr),
      discordMuteButton_(nullptr),
      discordMuteLabel_(nullptr),
      micIconContainer_(nullptr),
      micBody_(nullptr),
      micBracket_(nullptr),
      micStem_(nullptr),
      micBase_(nullptr),
      micSlash_(nullptr),
      discordDeafenButton_(nullptr),
      discordDeafenLabel_(nullptr),
      headphoneIconContainer_(nullptr),
      headphoneArc_(nullptr),
      headphoneLeft_(nullptr),
      headphoneRight_(nullptr),
      headphoneSlash_(nullptr),
      viewButton_(nullptr),
      viewLabel_(nullptr),
      viewImageObject_(nullptr),
      backgroundImageObject_(nullptr),
      queuePanel_(nullptr),
      queueHeading_(nullptr),
      queueSourceLabel_(nullptr),
      queueRows_{nullptr, nullptr, nullptr, nullptr},
      mixerPanel_(nullptr),
      mixerHeading_(nullptr),
      mixerRows_{nullptr, nullptr, nullptr, nullptr},
      mixerBars_{nullptr, nullptr, nullptr, nullptr},
      utilityPreviousButton_(nullptr),
      utilityPreviousLabel_(nullptr),
      utilitySelectButton_(nullptr),
      utilitySelectLabel_(nullptr),
      utilityNextButton_(nullptr),
      utilityNextLabel_(nullptr),
      queueHomeButton_(nullptr),
      queueHomeLabel_(nullptr),
      mixerDownButton_(nullptr),
      mixerDownLabel_(nullptr),
      mixerMuteButton_(nullptr),
      mixerMuteLabel_(nullptr),
      mixerUpButton_(nullptr),
      mixerUpLabel_(nullptr),
      displayedPlaying_(false),
      playPending_(false),
      expectedPlaying_(false),
      playStartedAtMs_(0),
      lastProgressUpdateMs_(0)
{
    instance_ = this;
}

void SpotifyUI::create(lv_obj_t* screen)
{
    lv_obj_add_event_cb(
        screen,
        screenGestureEvent,
        LV_EVENT_GESTURE,
        nullptr
    );

    lv_obj_set_style_bg_color(
        screen,
        lv_color_hex(BACKGROUND_COLOR),
        LV_PART_MAIN
    );


    backgroundImageObject_ = lv_img_create(screen);
    lv_obj_set_size(
        backgroundImageObject_,
        BackgroundImage::WIDTH,
        BackgroundImage::HEIGHT
    );
    lv_obj_set_pos(backgroundImageObject_, 0, 0);

    // Exact 1:1 800x480 image: no zoom, pivot, or interpolation.
    lv_img_set_zoom(backgroundImageObject_, 256);
    lv_img_set_antialias(backgroundImageObject_, false);
    lv_obj_set_style_img_opa(
        backgroundImageObject_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(
        backgroundImageObject_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_add_flag(
        backgroundImageObject_,
        LV_OBJ_FLAG_HIDDEN
    );
    lv_obj_clear_flag(
        backgroundImageObject_,
        LV_OBJ_FLAG_CLICKABLE
    );
    lv_obj_move_background(backgroundImageObject_);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, LV_PART_MAIN);

    sourceButton_ = lv_btn_create(screen);
    lv_obj_set_size(
        sourceButton_,
        SourceImage::WIDTH,
        SourceImage::HEIGHT
    );
    lv_obj_set_pos(sourceButton_, 520, 18);

    // The PC-rendered source image supplies the visible button.
    // Keep this LVGL parent fully transparent so it only handles touch.
    lv_obj_set_style_bg_opa(
        sourceButton_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        sourceButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(
        sourceButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_outline_width(
        sourceButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_pad_all(
        sourceButton_,
        0,
        LV_PART_MAIN
    );

    lv_obj_add_event_cb(
        sourceButton_,
        sourceEvent,
        LV_EVENT_ALL,
        nullptr
    );


    viewButton_ = lv_btn_create(screen);
    lv_obj_set_size(viewButton_, 110, 38);
    lv_obj_set_pos(viewButton_, 390, 18);
    lv_obj_set_style_radius(viewButton_, 19, LV_PART_MAIN);
    lv_obj_set_style_bg_color(
        viewButton_,
        lv_color_hex(PANEL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(viewButton_, 0, LV_PART_MAIN);
    lv_obj_add_event_cb(
        viewButton_,
        viewEvent,
        LV_EVENT_ALL,
        nullptr
    );

    viewLabel_ = lv_label_create(viewButton_);
    lv_label_set_text(viewLabel_, "View");
    lv_obj_center(viewLabel_);

    sourceLabel_ = lv_label_create(sourceButton_);
    lv_label_set_text(sourceLabel_, "Auto source");
    lv_obj_set_width(sourceLabel_, 220);
    lv_label_set_long_mode(sourceLabel_, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_align(
        sourceLabel_,
        LV_TEXT_ALIGN_CENTER,
        LV_PART_MAIN
    );
    lv_obj_set_style_text_color(
        sourceLabel_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        sourceLabel_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );
    lv_obj_center(sourceLabel_);
    lv_obj_add_flag(sourceLabel_, LV_OBJ_FLAG_HIDDEN);

    sourceImageObject_ = lv_img_create(sourceButton_);

    lv_obj_set_size(
        sourceImageObject_,
        SourceImage::WIDTH,
        SourceImage::HEIGHT
    );

    lv_obj_set_pos(sourceImageObject_, 0, 0);
    lv_obj_set_style_bg_opa(
        sourceImageObject_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        sourceImageObject_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(
        sourceImageObject_,
        0,
        LV_PART_MAIN
    );

    lv_obj_add_flag(
        sourceImageObject_,
        LV_OBJ_FLAG_HIDDEN
    );

    lv_obj_clear_flag(
        sourceImageObject_,
        LV_OBJ_FLAG_CLICKABLE
    );

    metadataImageObject_ = lv_img_create(screen);
    lv_obj_set_size(
        metadataImageObject_,
        MetadataImage::WIDTH,
        MetadataImage::HEIGHT
    );
    lv_obj_set_pos(metadataImageObject_, 290, 66);
    lv_obj_set_style_bg_opa(
        metadataImageObject_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        metadataImageObject_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(
        metadataImageObject_,
        0,
        LV_PART_MAIN
    );
    lv_obj_add_flag(
        metadataImageObject_,
        LV_OBJ_FLAG_HIDDEN
    );


    viewImageObject_ = lv_img_create(screen);
    lv_obj_set_size(
        viewImageObject_,
        ViewImage::WIDTH,
        ViewImage::HEIGHT
    );
    lv_obj_set_pos(viewImageObject_, 290, 70);
    lv_obj_add_flag(
        viewImageObject_,
        LV_OBJ_FLAG_HIDDEN
    );


    // V9 native Queue page. It uses LVGL labels instead of a streamed bitmap.
    queuePanel_ = lv_obj_create(screen);
    lv_obj_set_size(queuePanel_, 470, 160);
    lv_obj_set_pos(queuePanel_, 290, 70);
    // Give Queue its own compositor layer. A mostly opaque panel prevents
    // stale Now Playing pixels from showing through while retaining a hint of
    // the artwork background.
    lv_obj_set_style_bg_color(
        queuePanel_,
        lv_color_hex(0x121212),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(queuePanel_, LV_OPA_90, LV_PART_MAIN);
    lv_obj_set_style_radius(queuePanel_, 10, LV_PART_MAIN);
    lv_obj_set_style_border_width(queuePanel_, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(queuePanel_, 0, LV_PART_MAIN);
    lv_obj_clear_flag(queuePanel_, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(queuePanel_, LV_OBJ_FLAG_HIDDEN);

    queueHeading_ = lv_label_create(queuePanel_);
    lv_label_set_text(queueHeading_, "Queue");
    lv_obj_set_pos(queueHeading_, 8, 2);
    lv_obj_set_style_text_color(
        queueHeading_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        queueHeading_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );

    queueSourceLabel_ = lv_label_create(queuePanel_);
    lv_label_set_text(queueSourceLabel_, "");
    lv_obj_set_width(queueSourceLabel_, 300);
    lv_obj_set_pos(queueSourceLabel_, 160, 2);
    lv_obj_set_style_text_align(
        queueSourceLabel_,
        LV_TEXT_ALIGN_RIGHT,
        LV_PART_MAIN
    );
    lv_obj_set_style_text_color(
        queueSourceLabel_,
        lv_color_hex(0xB5BAC1),
        LV_PART_MAIN
    );

    for (uint8_t index = 0; index < 4; ++index)
    {
        queueRows_[index] = lv_label_create(queuePanel_);
        lv_obj_set_size(queueRows_[index], 454, 27);
        lv_obj_set_pos(queueRows_[index], 8, 30 + index * 31);
        lv_label_set_long_mode(
            queueRows_[index],
            LV_LABEL_LONG_DOT
        );
        lv_obj_set_style_pad_left(
            queueRows_[index],
            8,
            LV_PART_MAIN
        );
        lv_obj_set_style_pad_right(
            queueRows_[index],
            8,
            LV_PART_MAIN
        );
        lv_obj_set_style_pad_top(
            queueRows_[index],
            5,
            LV_PART_MAIN
        );
        lv_obj_set_style_radius(
            queueRows_[index],
            7,
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_opa(
            queueRows_[index],
            LV_OPA_30,
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_color(
            queueRows_[index],
            lv_color_hex(0x202225),
            LV_PART_MAIN
        );
        lv_obj_set_style_text_color(
            queueRows_[index],
            lv_color_white(),
            LV_PART_MAIN
        );
    }



    // V9 native Mixer page.
    mixerPanel_ = lv_obj_create(screen);
    lv_obj_set_size(mixerPanel_, 470, 160);
    lv_obj_set_pos(mixerPanel_, 290, 70);
    lv_obj_set_style_bg_opa(mixerPanel_, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(mixerPanel_, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(mixerPanel_, 0, LV_PART_MAIN);
    lv_obj_clear_flag(mixerPanel_, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_add_flag(mixerPanel_, LV_OBJ_FLAG_HIDDEN);

    mixerHeading_ = lv_label_create(mixerPanel_);
    lv_label_set_text(mixerHeading_, "Audio Mixer");
    lv_obj_set_pos(mixerHeading_, 8, 2);
    lv_obj_set_style_text_color(
        mixerHeading_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        mixerHeading_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );

    for (uint8_t index = 0; index < 4; ++index)
    {
        mixerRows_[index] = lv_label_create(mixerPanel_);
        lv_obj_set_size(mixerRows_[index], 310, 28);
        lv_obj_set_pos(mixerRows_[index], 8, 30 + index * 31);
        lv_label_set_long_mode(
            mixerRows_[index],
            LV_LABEL_LONG_DOT
        );
        lv_obj_set_style_pad_left(
            mixerRows_[index],
            8,
            LV_PART_MAIN
        );
        lv_obj_set_style_pad_top(
            mixerRows_[index],
            5,
            LV_PART_MAIN
        );
        lv_obj_set_style_radius(
            mixerRows_[index],
            7,
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_opa(
            mixerRows_[index],
            LV_OPA_20,
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_color(
            mixerRows_[index],
            lv_color_hex(0x202225),
            LV_PART_MAIN
        );
        lv_obj_set_style_text_color(
            mixerRows_[index],
            lv_color_white(),
            LV_PART_MAIN
        );

        mixerBars_[index] = lv_bar_create(mixerPanel_);
        lv_obj_set_size(mixerBars_[index], 125, 10);
        lv_obj_set_pos(mixerBars_[index], 330, 39 + index * 31);
        lv_bar_set_range(mixerBars_[index], 0, 100);
        lv_bar_set_value(mixerBars_[index], 0, LV_ANIM_OFF);
        lv_obj_set_style_bg_opa(
            mixerBars_[index],
            LV_OPA_30,
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_color(
            mixerBars_[index],
            lv_color_hex(0x4E5058),
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_color(
            mixerBars_[index],
            lv_color_hex(0x5865F2),
            LV_PART_INDICATOR
        );
    }

    // Utility-page navigation. These live below the PC-rendered page, so they
    // never overlap queue/mixer content.
    utilityPreviousButton_ = lv_btn_create(screen);
    lv_obj_set_size(utilityPreviousButton_, 90, 42);
    lv_obj_set_pos(utilityPreviousButton_, 320, 242);
    lv_obj_add_event_cb(
        utilityPreviousButton_,
        utilityPreviousEvent,
        LV_EVENT_RELEASED,
        nullptr
    );
    utilityPreviousLabel_ = lv_label_create(utilityPreviousButton_);
    lv_label_set_text(utilityPreviousLabel_, "Previous");
    lv_obj_center(utilityPreviousLabel_);

    utilitySelectButton_ = lv_btn_create(screen);
    lv_obj_set_size(utilitySelectButton_, 90, 42);
    lv_obj_set_pos(utilitySelectButton_, 430, 242);
    lv_obj_add_event_cb(
        utilitySelectButton_,
        utilitySelectEvent,
        LV_EVENT_RELEASED,
        nullptr
    );
    utilitySelectLabel_ = lv_label_create(utilitySelectButton_);
    lv_label_set_text(utilitySelectLabel_, "Select");
    lv_obj_center(utilitySelectLabel_);

    utilityNextButton_ = lv_btn_create(screen);
    lv_obj_set_size(utilityNextButton_, 90, 42);
    lv_obj_set_pos(utilityNextButton_, 540, 242);
    lv_obj_add_event_cb(
        utilityNextButton_,
        utilityNextEvent,
        LV_EVENT_RELEASED,
        nullptr
    );
    utilityNextLabel_ = lv_label_create(utilityNextButton_);
    lv_label_set_text(utilityNextLabel_, "Next");
    lv_obj_center(utilityNextLabel_);

    queueHomeButton_ = lv_btn_create(screen);
    lv_obj_set_size(queueHomeButton_, 90, 42);
    lv_obj_set_pos(queueHomeButton_, 650, 242);
    lv_obj_add_event_cb(
        queueHomeButton_,
        queueHomeEvent,
        LV_EVENT_RELEASED,
        nullptr
    );
    queueHomeLabel_ = lv_label_create(queueHomeButton_);
    lv_label_set_text(queueHomeLabel_, "Home");
    lv_obj_center(queueHomeLabel_);
    lv_obj_add_flag(queueHomeButton_, LV_OBJ_FLAG_HIDDEN);

    mixerDownButton_ = lv_btn_create(screen);
    lv_obj_set_size(mixerDownButton_, 56, 42);
    lv_obj_set_pos(mixerDownButton_, 645, 242);
    lv_obj_add_event_cb(
        mixerDownButton_,
        mixerDownEvent,
        LV_EVENT_RELEASED,
        nullptr
    );
    mixerDownLabel_ = lv_label_create(mixerDownButton_);
    lv_label_set_text(mixerDownLabel_, "-");
    lv_obj_center(mixerDownLabel_);

    mixerMuteButton_ = lv_btn_create(screen);
    lv_obj_set_size(mixerMuteButton_, 70, 42);
    lv_obj_set_pos(mixerMuteButton_, 430, 294);
    lv_obj_add_event_cb(
        mixerMuteButton_,
        mixerMuteEvent,
        LV_EVENT_RELEASED,
        nullptr
    );
    mixerMuteLabel_ = lv_label_create(mixerMuteButton_);
    lv_label_set_text(mixerMuteLabel_, "Mute");
    lv_obj_center(mixerMuteLabel_);

    mixerUpButton_ = lv_btn_create(screen);
    lv_obj_set_size(mixerUpButton_, 56, 42);
    lv_obj_set_pos(mixerUpButton_, 704, 242);
    lv_obj_add_event_cb(
        mixerUpButton_,
        mixerUpEvent,
        LV_EVENT_RELEASED,
        nullptr
    );
    mixerUpLabel_ = lv_label_create(mixerUpButton_);
    lv_label_set_text(mixerUpLabel_, "+");
    lv_obj_center(mixerUpLabel_);

    artworkContainer_ = lv_obj_create(screen);
    lv_obj_set_size(artworkContainer_, ARTWORK_SIZE, ARTWORK_SIZE);
    lv_obj_set_pos(artworkContainer_, 40, 70);
    lv_obj_set_style_bg_color(
        artworkContainer_,
        lv_color_hex(PANEL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(artworkContainer_, 0, LV_PART_MAIN);

    // The artwork bitmap is exactly the same size as this container.
    // Remove any theme/default padding so the image can reach every edge.
    lv_obj_set_style_pad_all(
        artworkContainer_,
        0,
        LV_PART_MAIN
    );

    lv_obj_set_style_radius(
        artworkContainer_,
        ARTWORK_RADIUS,
        LV_PART_MAIN
    );
    lv_obj_set_style_clip_corner(
        artworkContainer_,
        true,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(artworkContainer_, 18, LV_PART_MAIN);
    lv_obj_set_style_shadow_opa(
        artworkContainer_,
        LV_OPA_30,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_ofs_y(artworkContainer_, 6, LV_PART_MAIN);
    lv_obj_clear_flag(artworkContainer_, LV_OBJ_FLAG_SCROLLABLE);

    artworkImage_ = lv_img_create(artworkContainer_);
    lv_obj_set_size(
        artworkImage_,
        Artwork::WIDTH,
        Artwork::HEIGHT
    );
    lv_obj_set_style_radius(
        artworkImage_,
        ARTWORK_RADIUS,
        LV_PART_MAIN
    );
    lv_obj_set_style_clip_corner(
        artworkImage_,
        true,
        LV_PART_MAIN
    );
    // Pin the 210x210 image directly to the 210x210 container instead of
    // relying on centering. This prevents a theme/content-area offset from
    // exposing a thin strip of the container around the artwork.
    lv_obj_set_pos(artworkImage_, 0, 0);
    lv_obj_add_flag(artworkImage_, LV_OBJ_FLAG_HIDDEN);

    artworkText_ = lv_label_create(artworkContainer_);
    lv_label_set_text(artworkText_, LV_SYMBOL_AUDIO "\nWaiting for media...");
    lv_obj_set_width(artworkText_, 180);
    lv_obj_set_style_text_align(
        artworkText_,
        LV_TEXT_ALIGN_CENTER,
        LV_PART_MAIN
    );
    lv_obj_set_style_text_color(
        artworkText_,
        lv_color_hex(SECONDARY_TEXT_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        artworkText_,
        &lv_font_montserrat_16,
        LV_PART_MAIN
    );
    lv_obj_center(artworkText_);

    title_ = lv_label_create(screen);
    lv_obj_add_flag(title_, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(title_, "Song Title");
    lv_obj_set_width(title_, 300);
    lv_obj_set_pos(title_, 290, 68);
    lv_label_set_long_mode(title_, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_anim_time(title_, 8500, LV_PART_MAIN);
    lv_obj_set_style_text_color(title_, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_font(
        title_,
        &lv_font_montserrat_28,
        LV_PART_MAIN
    );

    artist_ = lv_label_create(screen);
    lv_obj_add_flag(artist_, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(artist_, "Artist");
    lv_obj_set_width(artist_, 470);
    lv_obj_set_pos(artist_, 290, 116);
    lv_label_set_long_mode(artist_, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_anim_time(artist_, 9000, LV_PART_MAIN);
    lv_obj_set_style_text_color(
        artist_,
        lv_color_hex(SECONDARY_TEXT_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        artist_,
        &lv_font_montserrat_18,
        LV_PART_MAIN
    );

    album_ = lv_label_create(screen);
    lv_obj_add_flag(album_, LV_OBJ_FLAG_HIDDEN);
    lv_label_set_text(album_, "Album");
    lv_obj_set_width(album_, 470);
    lv_obj_set_pos(album_, 290, 151);
    lv_label_set_long_mode(album_, LV_LABEL_LONG_SCROLL_CIRCULAR);
    lv_obj_set_style_anim_time(album_, 9500, LV_PART_MAIN);
    lv_obj_set_style_text_color(
        album_,
        lv_color_hex(0x858585),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        album_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );

    previousButton_ = lv_btn_create(screen);
    lv_obj_set_size(previousButton_, 72, 72);
    lv_obj_set_pos(previousButton_, 356, 188);
    lv_obj_set_style_bg_opa(
        previousButton_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(previousButton_, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(previousButton_, 0, LV_PART_MAIN);

    lv_obj_t* previousLabel = lv_label_create(previousButton_);
    lv_label_set_text(previousLabel, LV_SYMBOL_PREV);
    lv_obj_set_style_text_color(
        previousLabel,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        previousLabel,
        &lv_font_montserrat_24,
        LV_PART_MAIN
    );
    lv_obj_center(previousLabel);
    lv_obj_add_event_cb(
        previousButton_,
        previousEvent,
        LV_EVENT_RELEASED,
        nullptr
    );

    playButton_ = lv_btn_create(screen);
    lv_obj_set_size(playButton_, 72, 72);
    lv_obj_set_pos(playButton_, 455, 188);
    lv_obj_set_style_radius(playButton_, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(
        playButton_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(playButton_, 0, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(playButton_, 0, LV_PART_MAIN);

    playLabel_ = lv_label_create(playButton_);
    lv_label_set_text(playLabel_, LV_SYMBOL_PLAY);
    lv_obj_set_style_text_color(
        playLabel_,
        lv_color_black(),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        playLabel_,
        &lv_font_montserrat_32,
        LV_PART_MAIN
    );
    lv_obj_center(playLabel_);
    lv_obj_add_event_cb(
        playButton_,
        playPauseEvent,
        LV_EVENT_RELEASED,
        nullptr
    );

    nextButton_ = lv_btn_create(screen);
    lv_obj_set_size(nextButton_, 72, 72);
    lv_obj_set_pos(nextButton_, 556, 188);
    lv_obj_set_style_bg_opa(
        nextButton_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(nextButton_, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(nextButton_, 0, LV_PART_MAIN);

    lv_obj_t* nextLabel = lv_label_create(nextButton_);
    lv_label_set_text(nextLabel, LV_SYMBOL_NEXT);
    lv_obj_set_style_text_color(nextLabel, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_font(
        nextLabel,
        &lv_font_montserrat_24,
        LV_PART_MAIN
    );
    lv_obj_center(nextLabel);
    lv_obj_add_event_cb(
        nextButton_,
        nextEvent,
        LV_EVENT_RELEASED,
        nullptr
    );

    progressBar_ = lv_bar_create(screen);
    lv_obj_set_size(progressBar_, 430, 6);
    lv_obj_set_pos(progressBar_, 300, 304);
    lv_bar_set_range(progressBar_, 0, 1000);
    lv_bar_set_value(progressBar_, 0, LV_ANIM_OFF);
    lv_obj_set_style_radius(progressBar_, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_bg_color(
        progressBar_,
        lv_color_hex(PROGRESS_TRACK_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        progressBar_,
        lv_color_white(),
        LV_PART_INDICATOR
    );
    lv_obj_set_style_radius(
        progressBar_,
        LV_RADIUS_CIRCLE,
        LV_PART_INDICATOR
    );

    elapsed_ = lv_label_create(screen);
    lv_label_set_text(elapsed_, "0:00");
    lv_obj_set_pos(elapsed_, 300, 319);
    lv_obj_set_style_text_color(
        elapsed_,
        lv_color_hex(SECONDARY_TEXT_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        elapsed_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );

    duration_ = lv_label_create(screen);
    lv_label_set_text(duration_, "0:00");
    lv_obj_set_width(duration_, 80);
    lv_obj_set_pos(duration_, 650, 319);
    lv_obj_set_style_text_align(
        duration_,
        LV_TEXT_ALIGN_RIGHT,
        LV_PART_MAIN
    );
    lv_obj_set_style_text_color(
        duration_,
        lv_color_hex(SECONDARY_TEXT_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        duration_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );

    // Shuffle and Repeat are both status indicators and touch controls.
    shuffleButton_ = lv_btn_create(screen);
    lv_obj_set_size(shuffleButton_, 104, 38);
    lv_obj_set_pos(shuffleButton_, 305, 365);
    lv_obj_set_style_radius(shuffleButton_, 19, LV_PART_MAIN);
    lv_obj_set_style_bg_color(
        shuffleButton_,
        lv_color_hex(PANEL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(shuffleButton_, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(shuffleButton_, 0, LV_PART_MAIN);
    lv_obj_add_event_cb(
        shuffleButton_,
        shuffleEvent,
        LV_EVENT_RELEASED,
        nullptr
    );

    shuffleLabel_ = lv_label_create(shuffleButton_);
    lv_label_set_text(shuffleLabel_, "Shuffle");
    lv_obj_set_style_text_color(
        shuffleLabel_,
        lv_color_hex(INACTIVE_CONTROL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        shuffleLabel_,
        &lv_font_montserrat_16,
        LV_PART_MAIN
    );
    lv_obj_center(shuffleLabel_);

    repeatButton_ = lv_btn_create(screen);
    lv_obj_set_size(repeatButton_, 118, 38);
    lv_obj_set_pos(repeatButton_, 622, 365);
    lv_obj_set_style_radius(repeatButton_, 19, LV_PART_MAIN);
    lv_obj_set_style_bg_color(
        repeatButton_,
        lv_color_hex(PANEL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(repeatButton_, 0, LV_PART_MAIN);
    lv_obj_set_style_border_width(repeatButton_, 0, LV_PART_MAIN);
    lv_obj_add_event_cb(
        repeatButton_,
        repeatEvent,
        LV_EVENT_RELEASED,
        nullptr
    );

    repeatLabel_ = lv_label_create(repeatButton_);
    lv_label_set_text(repeatLabel_, "Repeat");
    lv_obj_set_style_text_color(
        repeatLabel_,
        lv_color_hex(INACTIVE_CONTROL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        repeatLabel_,
        &lv_font_montserrat_16,
        LV_PART_MAIN
    );
    lv_obj_center(repeatLabel_);

    // Discord voice connection status.
    voiceStatusDot_ = lv_obj_create(screen);
    lv_obj_set_size(voiceStatusDot_, 10, 10);
    lv_obj_set_pos(voiceStatusDot_, 40, 438);
    lv_obj_set_style_radius(
        voiceStatusDot_,
        LV_RADIUS_CIRCLE,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        voiceStatusDot_,
        lv_color_hex(0x666666),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(
        voiceStatusDot_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        voiceStatusDot_,
        0,
        LV_PART_MAIN
    );
    lv_obj_clear_flag(
        voiceStatusDot_,
        LV_OBJ_FLAG_SCROLLABLE
    );

    statusLabel_ = lv_label_create(screen);
    lv_label_set_text(statusLabel_, "Voice Disconnected");
    lv_obj_set_width(statusLabel_, 180);
    lv_obj_set_pos(statusLabel_, 58, 432);
    lv_label_set_long_mode(statusLabel_, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_color(
        statusLabel_,
        lv_color_hex(SECONDARY_TEXT_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        statusLabel_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );

    batteryLabel_ = lv_label_create(screen);
    lv_label_set_text(batteryLabel_, "");
    lv_obj_set_width(batteryLabel_, 220);
    lv_obj_set_pos(batteryLabel_, 255, 432);
    lv_label_set_long_mode(batteryLabel_, LV_LABEL_LONG_DOT);
    lv_obj_set_style_text_align(
        batteryLabel_,
        LV_TEXT_ALIGN_LEFT,
        LV_PART_MAIN
    );
    lv_obj_set_style_text_color(
        batteryLabel_,
        lv_color_hex(SECONDARY_TEXT_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_text_font(
        batteryLabel_,
        &lv_font_montserrat_14,
        LV_PART_MAIN
    );

    // Discord-style microphone button.
    discordMuteButton_ = lv_btn_create(screen);
    lv_obj_set_size(discordMuteButton_, 70, 42);
    lv_obj_set_pos(discordMuteButton_, 585, 418);
    lv_obj_set_style_radius(
        discordMuteButton_,
        21,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        discordMuteButton_,
        lv_color_hex(PANEL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(
        discordMuteButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        discordMuteButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_pad_all(
        discordMuteButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_add_event_cb(
        discordMuteButton_,
        discordMuteEvent,
        LV_EVENT_RELEASED,
        nullptr
    );

    discordMuteLabel_ = lv_label_create(discordMuteButton_);
    lv_label_set_text(discordMuteLabel_, "");
    lv_obj_add_flag(
        discordMuteLabel_,
        LV_OBJ_FLAG_HIDDEN
    );

    // A fixed 32x32 coordinate system keeps every mic element centered.
    micIconContainer_ = lv_obj_create(discordMuteButton_);
    lv_obj_set_size(micIconContainer_, 32, 32);
    lv_obj_center(micIconContainer_);
    lv_obj_set_style_bg_opa(
        micIconContainer_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        micIconContainer_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_pad_all(
        micIconContainer_,
        0,
        LV_PART_MAIN
    );
    lv_obj_clear_flag(
        micIconContainer_,
        LV_OBJ_FLAG_SCROLLABLE
    );
    lv_obj_clear_flag(
        micIconContainer_,
        LV_OBJ_FLAG_CLICKABLE
    );

    // Microphone capsule.
    micBody_ = lv_obj_create(micIconContainer_);
    lv_obj_set_size(micBody_, 10, 17);
    lv_obj_set_pos(micBody_, 11, 2);
    lv_obj_set_style_radius(
        micBody_,
        5,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        micBody_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(
        micBody_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        micBody_,
        0,
        LV_PART_MAIN
    );
    lv_obj_clear_flag(micBody_, LV_OBJ_FLAG_SCROLLABLE);

    // U-shaped microphone bracket.
    micBracket_ = lv_arc_create(micIconContainer_);
    lv_obj_set_size(micBracket_, 22, 22);
    lv_obj_set_pos(micBracket_, 5, 7);
    lv_arc_set_bg_angles(micBracket_, 0, 180);
    lv_obj_set_style_arc_width(
        micBracket_,
        2,
        LV_PART_MAIN
    );
    lv_obj_set_style_arc_color(
        micBracket_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_arc_opa(
        micBracket_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_arc_opa(
        micBracket_,
        LV_OPA_TRANSP,
        LV_PART_INDICATOR
    );
    lv_obj_set_style_bg_opa(
        micBracket_,
        LV_OPA_TRANSP,
        LV_PART_KNOB
    );
    lv_obj_clear_flag(micBracket_, LV_OBJ_FLAG_CLICKABLE);

    micStem_ = lv_obj_create(micIconContainer_);
    lv_obj_set_size(micStem_, 2, 6);
    lv_obj_set_pos(micStem_, 15, 23);
    lv_obj_set_style_bg_color(
        micStem_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(
        micStem_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(micStem_, 0, LV_PART_MAIN);
    lv_obj_clear_flag(micStem_, LV_OBJ_FLAG_SCROLLABLE);

    micBase_ = lv_obj_create(micIconContainer_);
    lv_obj_set_size(micBase_, 12, 2);
    lv_obj_set_pos(micBase_, 10, 29);
    lv_obj_set_style_radius(
        micBase_,
        1,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        micBase_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(
        micBase_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(micBase_, 0, LV_PART_MAIN);
    lv_obj_clear_flag(micBase_, LV_OBJ_FLAG_SCROLLABLE);

    // Slash uses the same 32x32 coordinate system and is explicitly foreground.
    static lv_point_t micSlashPoints[2] = {
        {4, 3},
        {28, 29}
    };
    micSlash_ = lv_line_create(micIconContainer_);
    lv_obj_set_size(micSlash_, 32, 32);
    lv_obj_set_pos(micSlash_, 0, 0);
    lv_line_set_points(
        micSlash_,
        micSlashPoints,
        2
    );
    lv_obj_set_style_line_width(
        micSlash_,
        3,
        LV_PART_MAIN
    );
    lv_obj_set_style_line_color(
        micSlash_,
        lv_color_hex(0xED4245),
        LV_PART_MAIN
    );
    lv_obj_set_style_line_rounded(
        micSlash_,
        true,
        LV_PART_MAIN
    );
    lv_obj_add_flag(micSlash_, LV_OBJ_FLAG_HIDDEN);
    lv_obj_clear_flag(micSlash_, LV_OBJ_FLAG_CLICKABLE);
    lv_obj_move_foreground(micSlash_);

    // Discord-style deafen/headphones button.
    discordDeafenButton_ = lv_btn_create(screen);
    lv_obj_set_size(discordDeafenButton_, 70, 42);
    lv_obj_set_pos(discordDeafenButton_, 670, 418);
    lv_obj_set_style_radius(
        discordDeafenButton_,
        21,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        discordDeafenButton_,
        lv_color_hex(PANEL_COLOR),
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_width(
        discordDeafenButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        discordDeafenButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_pad_all(
        discordDeafenButton_,
        0,
        LV_PART_MAIN
    );
    lv_obj_add_event_cb(
        discordDeafenButton_,
        discordDeafenEvent,
        LV_EVENT_RELEASED,
        nullptr
    );

    discordDeafenLabel_ = lv_label_create(discordDeafenButton_);
    lv_label_set_text(discordDeafenLabel_, "");
    lv_obj_add_flag(
        discordDeafenLabel_,
        LV_OBJ_FLAG_HIDDEN
    );

    headphoneIconContainer_ = lv_obj_create(discordDeafenButton_);
    lv_obj_set_size(headphoneIconContainer_, 32, 32);
    lv_obj_center(headphoneIconContainer_);
    lv_obj_set_style_bg_opa(
        headphoneIconContainer_,
        LV_OPA_TRANSP,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        headphoneIconContainer_,
        0,
        LV_PART_MAIN
    );
    lv_obj_set_style_pad_all(
        headphoneIconContainer_,
        0,
        LV_PART_MAIN
    );
    lv_obj_clear_flag(
        headphoneIconContainer_,
        LV_OBJ_FLAG_SCROLLABLE
    );
    lv_obj_clear_flag(
        headphoneIconContainer_,
        LV_OBJ_FLAG_CLICKABLE
    );

    // Headband and earcups follow Discord's compact headset proportions.
    headphoneArc_ = lv_arc_create(headphoneIconContainer_);
    lv_obj_set_size(headphoneArc_, 28, 28);
    lv_obj_set_pos(headphoneArc_, 2, 2);
    lv_arc_set_bg_angles(headphoneArc_, 180, 360);
    lv_obj_set_style_arc_width(
        headphoneArc_,
        3,
        LV_PART_MAIN
    );
    lv_obj_set_style_arc_color(
        headphoneArc_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_arc_opa(
        headphoneArc_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_arc_opa(
        headphoneArc_,
        LV_OPA_TRANSP,
        LV_PART_INDICATOR
    );
    lv_obj_set_style_bg_opa(
        headphoneArc_,
        LV_OPA_TRANSP,
        LV_PART_KNOB
    );
    lv_obj_clear_flag(headphoneArc_, LV_OBJ_FLAG_CLICKABLE);

    headphoneLeft_ = lv_obj_create(headphoneIconContainer_);
    lv_obj_set_size(headphoneLeft_, 7, 13);
    lv_obj_set_pos(headphoneLeft_, 2, 15);
    lv_obj_set_style_radius(
        headphoneLeft_,
        3,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        headphoneLeft_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(
        headphoneLeft_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        headphoneLeft_,
        0,
        LV_PART_MAIN
    );
    lv_obj_clear_flag(
        headphoneLeft_,
        LV_OBJ_FLAG_SCROLLABLE
    );

    headphoneRight_ = lv_obj_create(headphoneIconContainer_);
    lv_obj_set_size(headphoneRight_, 7, 13);
    lv_obj_set_pos(headphoneRight_, 23, 15);
    lv_obj_set_style_radius(
        headphoneRight_,
        3,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        headphoneRight_,
        lv_color_white(),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(
        headphoneRight_,
        LV_OPA_COVER,
        LV_PART_MAIN
    );
    lv_obj_set_style_border_width(
        headphoneRight_,
        0,
        LV_PART_MAIN
    );
    lv_obj_clear_flag(
        headphoneRight_,
        LV_OBJ_FLAG_SCROLLABLE
    );

    static lv_point_t headphoneSlashPoints[2] = {
        {3, 3},
        {29, 29}
    };
    headphoneSlash_ = lv_line_create(headphoneIconContainer_);
    lv_obj_set_size(headphoneSlash_, 32, 32);
    lv_obj_set_pos(headphoneSlash_, 0, 0);
    lv_line_set_points(
        headphoneSlash_,
        headphoneSlashPoints,
        2
    );
    lv_obj_set_style_line_width(
        headphoneSlash_,
        3,
        LV_PART_MAIN
    );
    lv_obj_set_style_line_color(
        headphoneSlash_,
        lv_color_hex(0xED4245),
        LV_PART_MAIN
    );
    lv_obj_set_style_line_rounded(
        headphoneSlash_,
        true,
        LV_PART_MAIN
    );
    lv_obj_add_flag(
        headphoneSlash_,
        LV_OBJ_FLAG_HIDDEN
    );
    lv_obj_clear_flag(
        headphoneSlash_,
        LV_OBJ_FLAG_CLICKABLE
    );
    lv_obj_move_foreground(headphoneSlash_);

    updateStatusArea();
    state_.viewMode = "now_playing";
    updatePageVisibility();
}

void SpotifyUI::attachArtwork(Artwork& artwork)
{
    artwork.attach(artworkImage_, artworkText_);
}


void SpotifyUI::attachMetadataImage(MetadataImage& metadataImage)
{
    metadataImage.attach(metadataImageObject_);
}


void SpotifyUI::attachSourceImage(SourceImage& sourceImage)
{
    sourceImage.attach(sourceImageObject_);
}


void SpotifyUI::attachViewImage(ViewImage& viewImage)
{
    viewImage.attach(viewImageObject_);
}


void SpotifyUI::attachBackgroundImage(
    BackgroundImage& backgroundImage
)
{
    backgroundImage.attach(backgroundImageObject_);
}

void SpotifyUI::applyState(const AppState& state)
{
    const AppState previous = state_;
    const bool firstState = previous.receivedAtMs == 0;

    const bool pageChanged =
        firstState ||
        previous.viewMode != state.viewMode;

    const bool metadataChanged =
        firstState ||
        previous.spotifyConnected != state.spotifyConnected ||
        previous.title != state.title ||
        previous.artist != state.artist ||
        previous.album != state.album;

    const bool sourceChanged =
        firstState ||
        previous.application != state.application;

    const bool playbackChanged =
        firstState ||
        previous.playing != state.playing;

    const bool modeChanged =
        firstState ||
        previous.shuffle != state.shuffle ||
        previous.repeat != state.repeat;

    const bool statusChanged =
        firstState ||
        statusStateChanged(previous, state);

    const bool queueChanged =
        firstState ||
        queueStateChanged(previous, state);

    const bool mixerChanged =
        firstState ||
        mixerStateChanged(previous, state);

    const bool progressChanged =
        firstState ||
        previous.positionMs != state.positionMs ||
        previous.durationMs != state.durationMs ||
        previous.playing != state.playing;

    state_ = state;

    if (pageChanged)
    {
        updatePageVisibility();
    }

    if (metadataChanged)
    {
        if (state.spotifyConnected)
        {
            lv_label_set_text(
                title_,
                state.title.length() > 0
                    ? state.title.c_str()
                    : "Unknown title"
            );
            lv_label_set_text(
                artist_,
                state.artist.length() > 0
                    ? state.artist.c_str()
                    : "Unknown artist"
            );
            lv_label_set_text(
                album_,
                state.album.length() > 0
                    ? state.album.c_str()
                    : "Unknown album"
            );
        }
        else
        {
            lv_label_set_text(title_, "Media not connected");
            lv_label_set_text(
                artist_,
                "Start playback on your computer"
            );
            lv_label_set_text(album_, "");
        }
    }

    if (sourceChanged)
    {
        updateSourceButton();
    }

    if (playbackChanged || playPending_)
    {
        if (!playPending_)
        {
            updatePlayPauseIcon(state.playing);
        }
        else if (state.playing == expectedPlaying_)
        {
            updatePlayPauseIcon(state.playing);
            setPlayPending(false);
        }
    }

    if (modeChanged)
    {
        updateModeIndicators();
    }

    if (statusChanged)
    {
        updateStatusArea();
    }

    if (queueChanged)
    {
        updateNativeQueue();
    }

    if (mixerChanged)
    {
        updateNativeMixer();
    }

    if (progressChanged)
    {
        updateProgressNow(true);
    }
}

void SpotifyUI::updateSourceButton()
{
    String source = state_.application;
    source.trim();

    if (source.isEmpty())
    {
        source = "Auto";
    }

    // The visible source text is PC-rendered into sourceImageObject_.
    // Keep this function for state compatibility.
}

void SpotifyUI::setObjectVisible(
    lv_obj_t* object,
    bool visible
)
{
    if (object == nullptr)
    {
        return;
    }

    if (visible)
    {
        lv_obj_clear_flag(object, LV_OBJ_FLAG_HIDDEN);
    }
    else
    {
        lv_obj_add_flag(object, LV_OBJ_FLAG_HIDDEN);
    }
}
