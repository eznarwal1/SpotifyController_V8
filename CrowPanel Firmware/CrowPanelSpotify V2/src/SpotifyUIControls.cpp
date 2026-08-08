#include "SpotifyUI.h"

#include "Controls.h"

namespace
{
constexpr uint32_t PANEL_COLOR = 0x282828;
constexpr uint32_t INACTIVE_CONTROL_COLOR = 0xB3B3B3;
constexpr uint32_t ACTIVE_CONTROL_COLOR = 0x1DB954;
constexpr uint32_t PROGRESS_REFRESH_MS = 33;
}

void SpotifyUI::updateStatusArea()
{
    const lv_color_t connectedColor = lv_color_hex(0x23A55A);
    const lv_color_t disconnectedColor = lv_color_hex(0x666666);
    const lv_color_t normalIconColor = lv_color_white();
    const lv_color_t disabledIconColor = lv_color_hex(0x777777);
    const lv_color_t mutedColor = lv_color_hex(0xED4245);

    lv_label_set_text(
        statusLabel_,
        state_.discordCallActive
            ? "Voice Connected"
            : "Voice Disconnected"
    );

    lv_obj_set_style_bg_color(
        voiceStatusDot_,
        state_.discordCallActive
            ? connectedColor
            : disconnectedColor,
        LV_PART_MAIN
    );

    String batteryText;

    if (state_.batteryPresent)
    {
        batteryText = "Battery ";
        batteryText += String(state_.batteryPercent);
        batteryText += "%";

        if (state_.batteryCharging)
        {
            batteryText += " Charging";
        }
    }

    lv_label_set_text(
        batteryLabel_,
        batteryText.c_str()
    );

    const lv_color_t microphoneColor =
        !state_.discordCallActive
            ? disabledIconColor
            : (
                state_.discordMuted
                    ? mutedColor
                    : normalIconColor
            );

    const lv_color_t headphoneColor =
        !state_.discordCallActive
            ? disabledIconColor
            : (
                state_.discordDeafened
                    ? mutedColor
                    : normalIconColor
            );

    // Microphone icon.
    lv_obj_set_style_bg_color(
        micBody_,
        microphoneColor,
        LV_PART_MAIN
    );
    lv_obj_set_style_arc_color(
        micBracket_,
        microphoneColor,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        micStem_,
        microphoneColor,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        micBase_,
        microphoneColor,
        LV_PART_MAIN
    );

    // Headphones icon.
    lv_obj_set_style_arc_color(
        headphoneArc_,
        headphoneColor,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        headphoneLeft_,
        headphoneColor,
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        headphoneRight_,
        headphoneColor,
        LV_PART_MAIN
    );

    // Show a red slash over the microphone while muted.
    if (state_.discordCallActive && state_.discordMuted)
    {
        lv_obj_clear_flag(
            micSlash_,
            LV_OBJ_FLAG_HIDDEN
        );
        lv_obj_set_style_line_color(
            micSlash_,
            mutedColor,
            LV_PART_MAIN
        );
        lv_obj_move_foreground(micSlash_);

        lv_obj_set_style_bg_color(
            discordMuteButton_,
            lv_color_hex(0x3A2325),
            LV_PART_MAIN
        );
    }
    else
    {
        lv_obj_add_flag(
            micSlash_,
            LV_OBJ_FLAG_HIDDEN
        );

        lv_obj_set_style_bg_color(
            discordMuteButton_,
            lv_color_hex(PANEL_COLOR),
            LV_PART_MAIN
        );
    }

    // Show a red slash over the headphones while deafened.
    if (state_.discordCallActive && state_.discordDeafened)
    {
        lv_obj_clear_flag(
            headphoneSlash_,
            LV_OBJ_FLAG_HIDDEN
        );
        lv_obj_set_style_line_color(
            headphoneSlash_,
            mutedColor,
            LV_PART_MAIN
        );
        lv_obj_move_foreground(headphoneSlash_);

        lv_obj_set_style_bg_color(
            discordDeafenButton_,
            lv_color_hex(0x3A2325),
            LV_PART_MAIN
        );
    }
    else
    {
        lv_obj_add_flag(
            headphoneSlash_,
            LV_OBJ_FLAG_HIDDEN
        );

        lv_obj_set_style_bg_color(
            discordDeafenButton_,
            lv_color_hex(PANEL_COLOR),
            LV_PART_MAIN
        );
    }

    if (state_.discordCallActive)
    {
        lv_obj_clear_state(
            discordMuteButton_,
            LV_STATE_DISABLED
        );
        lv_obj_clear_state(
            discordDeafenButton_,
            LV_STATE_DISABLED
        );

        lv_obj_set_style_opa(
            discordMuteButton_,
            LV_OPA_COVER,
            LV_PART_MAIN
        );
        lv_obj_set_style_opa(
            discordDeafenButton_,
            LV_OPA_COVER,
            LV_PART_MAIN
        );
    }
    else
    {
        lv_obj_add_state(
            discordMuteButton_,
            LV_STATE_DISABLED
        );
        lv_obj_add_state(
            discordDeafenButton_,
            LV_STATE_DISABLED
        );

        lv_obj_set_style_opa(
            discordMuteButton_,
            LV_OPA_50,
            LV_PART_MAIN
        );
        lv_obj_set_style_opa(
            discordDeafenButton_,
            LV_OPA_50,
            LV_PART_MAIN
        );
    }
}

void SpotifyUI::discordMuteEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"discord_mute\"}"
        );
    }
}

void SpotifyUI::discordDeafenEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"discord_deafen\"}"
        );
    }
}

void SpotifyUI::updateModeIndicators()
{
    const bool repeatActive =
        !state_.repeat.equalsIgnoreCase("None") &&
        state_.repeat.length() > 0;

    lv_obj_set_style_text_color(
        shuffleLabel_,
        lv_color_hex(
            state_.shuffle
                ? ACTIVE_CONTROL_COLOR
                : INACTIVE_CONTROL_COLOR
        ),
        LV_PART_MAIN
    );

    lv_obj_set_style_text_color(
        repeatLabel_,
        lv_color_hex(
            repeatActive
                ? ACTIVE_CONTROL_COLOR
                : INACTIVE_CONTROL_COLOR
        ),
        LV_PART_MAIN
    );

    if (state_.repeat.equalsIgnoreCase("Track"))
    {
        lv_label_set_text(repeatLabel_, "Repeat 1");
    }
    else if (state_.repeat.equalsIgnoreCase("List"))
    {
        lv_label_set_text(repeatLabel_, "Repeat All");
    }
    else
    {
        lv_label_set_text(repeatLabel_, "Repeat");
    }
}

void SpotifyUI::updatePlayPauseIcon(bool playing)
{
    displayedPlaying_ = playing;
    lv_label_set_text(
        playLabel_,
        playing ? LV_SYMBOL_PAUSE : LV_SYMBOL_PLAY
    );
    lv_obj_center(playLabel_);
}

void SpotifyUI::setPlayPending(bool pending)
{
    playPending_ = pending;
    lv_obj_set_style_bg_color(
        playButton_,
        pending ? lv_color_hex(0xB3B3B3) : lv_color_white(),
        LV_PART_MAIN
    );
}

void SpotifyUI::playPauseEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) != LV_EVENT_RELEASED ||
        instance_ == nullptr)
    {
        return;
    }

    instance_->expectedPlaying_ = !instance_->displayedPlaying_;
    instance_->playStartedAtMs_ = millis();
    instance_->updatePlayPauseIcon(instance_->expectedPlaying_);
    instance_->setPlayPending(true);
    Controls::sendPlayPause();
}

void SpotifyUI::previousEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Controls::sendPrevious();
    }
}

void SpotifyUI::nextEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Controls::sendNext();
    }
}

void SpotifyUI::sourceEvent(lv_event_t* event)
{
    const lv_event_code_t code = lv_event_get_code(event);

    if (code == LV_EVENT_SHORT_CLICKED)
    {
        Serial.println("{\"type\":\"command\",\"command\":\"source\"}");
    }
    else if (code == LV_EVENT_LONG_PRESSED)
    {
        Serial.println("{\"type\":\"command\",\"command\":\"source_auto\"}");
    }
}

void SpotifyUI::utilityPreviousEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"utility_previous\"}"
        );
    }
}

void SpotifyUI::utilitySelectEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"utility_select\"}"
        );
    }
}

void SpotifyUI::utilityNextEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"utility_next\"}"
        );
    }
}

void SpotifyUI::queueHomeEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"queue_home\"}"
        );
    }
}

void SpotifyUI::mixerDownEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"mixer_volume_down\"}"
        );
    }
}

void SpotifyUI::mixerMuteEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"mixer_mute\"}"
        );
    }
}

void SpotifyUI::mixerUpEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) == LV_EVENT_RELEASED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"mixer_volume_up\"}"
        );
    }
}

void SpotifyUI::screenGestureEvent(lv_event_t* event)
{
    if (lv_event_get_code(event) != LV_EVENT_GESTURE)
    {
        return;
    }

    lv_indev_t* input = lv_indev_get_act();
    if (input == nullptr)
    {
        return;
    }

    const lv_dir_t direction = lv_indev_get_gesture_dir(input);

    if (direction == LV_DIR_LEFT)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"view_next\"}"
        );
    }
    else if (direction == LV_DIR_RIGHT)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"view_previous\"}"
        );
    }
}

void SpotifyUI::viewEvent(lv_event_t* event)
{
    const lv_event_code_t code = lv_event_get_code(event);

    if (code == LV_EVENT_SHORT_CLICKED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"view_next\"}"
        );
    }
    else if (code == LV_EVENT_LONG_PRESSED)
    {
        Serial.println(
            "{\"type\":\"command\",\"command\":\"view_previous\"}"
        );
    }
}

void SpotifyUI::formatTime(
    uint32_t milliseconds,
    char* output,
    size_t outputSize
)
{
    const uint32_t totalSeconds = milliseconds / 1000U;
    snprintf(
        output,
        outputSize,
        "%lu:%02lu",
        static_cast<unsigned long>(totalSeconds / 60U),
        static_cast<unsigned long>(totalSeconds % 60U)
    );
}

void SpotifyUI::updateProgressNow(bool force)
{
    const uint32_t now = millis();

    if (!force && now - lastProgressUpdateMs_ < PROGRESS_REFRESH_MS)
    {
        return;
    }

    lastProgressUpdateMs_ = now;
    uint32_t displayedPosition = state_.positionMs;

    if (state_.playing && state_.durationMs > 0U)
    {
        displayedPosition += now - state_.receivedAtMs;
    }

    if (state_.durationMs > 0U && displayedPosition > state_.durationMs)
    {
        displayedPosition = state_.durationMs;
    }

    const int32_t progress =
        state_.durationMs > 0U
            ? static_cast<int32_t>(
                static_cast<uint64_t>(displayedPosition) * 1000ULL /
                state_.durationMs
            )
            : 0;

    lv_bar_set_value(progressBar_, progress, LV_ANIM_OFF);

    char elapsedText[16];
    char durationText[16];
    formatTime(displayedPosition, elapsedText, sizeof(elapsedText));
    formatTime(state_.durationMs, durationText, sizeof(durationText));
    lv_label_set_text(elapsed_, elapsedText);
    lv_label_set_text(duration_, durationText);
}

void SpotifyUI::updateProgress()
{
    if (playPending_ && millis() - playStartedAtMs_ > 1500U)
    {
        setPlayPending(false);
    }

    updateProgressNow(false);
}
