#include "SpotifyUI.h"

void SpotifyUI::updatePageVisibility()
{
    const bool nowPlaying =
        state_.viewMode.equalsIgnoreCase("now_playing");
    const bool utilityPage = !nowPlaying;

    // The background is already behind the UI. Avoid reordering the full
    // LVGL object tree on every page-state update.

    // Navigation stays available on every page.
    setObjectVisible(viewButton_, true);
    setObjectVisible(sourceButton_, true);

    // Artwork, metadata, playback controls, progress, Discord controls,
    // and status all share the Now Playing page.
    setObjectVisible(artworkContainer_, nowPlaying);
    setObjectVisible(metadataImageObject_, nowPlaying);
    setObjectVisible(previousButton_, nowPlaying);
    setObjectVisible(playButton_, nowPlaying);
    setObjectVisible(nextButton_, nowPlaying);
    setObjectVisible(progressBar_, nowPlaying);
    setObjectVisible(elapsed_, nowPlaying);
    setObjectVisible(duration_, nowPlaying);
    setObjectVisible(shuffleButton_, nowPlaying);
    setObjectVisible(repeatButton_, nowPlaying);
    setObjectVisible(voiceStatusDot_, nowPlaying);
    setObjectVisible(statusLabel_, nowPlaying);
    setObjectVisible(batteryLabel_, nowPlaying);
    setObjectVisible(discordMuteButton_, nowPlaying);
    setObjectVisible(discordDeafenButton_, nowPlaying);

    const bool queuePage =
        state_.viewMode.equalsIgnoreCase("queue");

    const bool mixerPage =
        state_.viewMode.equalsIgnoreCase("mixer");

    const bool discordPage =
        state_.viewMode.equalsIgnoreCase("discord");

    const bool settingsPage =
        state_.viewMode.equalsIgnoreCase("settings");

    // V9 Queue, Mixer, and Discord are native. Themes still uses the legacy bitmap.
    setObjectVisible(
        viewImageObject_,
        utilityPage && !queuePage && !mixerPage && !discordPage
    );
    setObjectVisible(queuePanel_, queuePage);


    setObjectVisible(mixerPanel_, mixerPage);
    setObjectVisible(discordPanel_, discordPage);
    const bool selectableUtility =
        queuePage ||
        mixerPage ||
        settingsPage ||
        state_.viewMode.equalsIgnoreCase("themes");

    setObjectVisible(
        utilityPreviousButton_,
        selectableUtility
    );
    setObjectVisible(
        utilitySelectButton_,
        selectableUtility
    );
    setObjectVisible(
        utilityNextButton_,
        selectableUtility
    );

    setObjectVisible(
        queueHomeButton_,
        queuePage
    );

    setObjectVisible(mixerDownButton_, mixerPage);
    setObjectVisible(mixerMuteButton_, mixerPage);
    setObjectVisible(mixerUpButton_, mixerPage);

    if (nowPlaying)
    {
        lv_label_set_text(viewLabel_, "Now");
    }
    else if (state_.viewMode.equalsIgnoreCase("queue"))
    {
        lv_label_set_text(viewLabel_, "Queue");
    }
    else if (state_.viewMode.equalsIgnoreCase("mixer"))
    {
        lv_label_set_text(viewLabel_, "Mixer");
    }
    else if (state_.viewMode.equalsIgnoreCase("discord"))
    {
        lv_label_set_text(viewLabel_, "Discord");
    }
    else if (settingsPage)
    {
        lv_label_set_text(viewLabel_, "Settings");
    }
    else if (state_.viewMode.equalsIgnoreCase("themes"))
    {
        lv_label_set_text(viewLabel_, "Themes");
    }
    else
    {
        lv_label_set_text(viewLabel_, "View");
    }

    /*
     * Page changes are infrequent. Invalidate once after all objects have
     * been shown/hidden so LVGL clears stale pixels in one coordinated pass.
     */
    lv_obj_invalidate(lv_scr_act());
}

void SpotifyUI::updateNativeQueue()
{
    if (queuePanel_ == nullptr)
    {
        return;
    }

    lv_label_set_text(
        queueSourceLabel_,
        state_.queueSource.isEmpty()
            ? "No queue source"
            : state_.queueSource.c_str()
    );

    if (state_.queueCount == 0)
    {
        lv_label_set_text(
            queueRows_[0],
            "Open Spotify Web Queue and leave it visible"
        );
        lv_obj_set_style_bg_opa(
            queueRows_[0],
            LV_OPA_20,
            LV_PART_MAIN
        );

        for (uint8_t row = 1; row < 4; ++row)
        {
            lv_label_set_text(queueRows_[row], "");
            lv_obj_set_style_bg_opa(
                queueRows_[row],
                LV_OPA_TRANSP,
                LV_PART_MAIN
            );
        }

        return;
    }

    int start = static_cast<int>(state_.queueSelectedIndex) - 1;
    start = constrain(
        start,
        0,
        max(0, static_cast<int>(state_.queueCount) - 4)
    );

    for (uint8_t row = 0; row < 4; ++row)
    {
        const int queueIndex = start + row;

        if (queueIndex >= state_.queueCount)
        {
            lv_label_set_text(queueRows_[row], "");
            lv_obj_set_style_bg_opa(
                queueRows_[row],
                LV_OPA_TRANSP,
                LV_PART_MAIN
            );
            continue;
        }

        lv_label_set_text(
            queueRows_[row],
            state_.queueEntries[queueIndex].c_str()
        );

        const bool selected =
            queueIndex == state_.queueSelectedIndex;

        lv_obj_set_style_bg_opa(
            queueRows_[row],
            selected ? LV_OPA_70 : LV_OPA_20,
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_color(
            queueRows_[row],
            selected
                ? lv_color_hex(0x5865F2)
                : lv_color_hex(0x202225),
            LV_PART_MAIN
        );
    }
}

void SpotifyUI::updateNativeMixer()
{
    if (mixerPanel_ == nullptr)
    {
        return;
    }

    if (state_.mixerCount == 0)
    {
        lv_label_set_text(
            mixerRows_[0],
            "No controllable audio sessions"
        );
        lv_bar_set_value(
            mixerBars_[0],
            0,
            LV_ANIM_OFF
        );

        for (uint8_t row = 1; row < 4; ++row)
        {
            lv_label_set_text(mixerRows_[row], "");
            lv_bar_set_value(
                mixerBars_[row],
                0,
                LV_ANIM_OFF
            );
        }

        return;
    }

    int start = static_cast<int>(state_.mixerSelectedIndex) - 1;
    start = constrain(
        start,
        0,
        max(0, static_cast<int>(state_.mixerCount) - 4)
    );

    for (uint8_t row = 0; row < 4; ++row)
    {
        const int mixerIndex = start + row;

        if (mixerIndex >= state_.mixerCount)
        {
            lv_label_set_text(mixerRows_[row], "");
            lv_bar_set_value(
                mixerBars_[row],
                0,
                LV_ANIM_OFF
            );
            continue;
        }

        String label = state_.mixerEntries[mixerIndex];
        label += "  ";
        label += String(state_.mixerVolumes[mixerIndex]);
        label += "%";

        if (state_.mixerMuted[mixerIndex])
        {
            label += " [Muted]";
        }

        lv_label_set_text(
            mixerRows_[row],
            label.c_str()
        );
        lv_bar_set_value(
            mixerBars_[row],
            state_.mixerVolumes[mixerIndex],
            LV_ANIM_OFF
        );

        const bool selected =
            mixerIndex == state_.mixerSelectedIndex;

        lv_obj_set_style_bg_opa(
            mixerRows_[row],
            selected ? LV_OPA_70 : LV_OPA_20,
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_color(
            mixerRows_[row],
            selected
                ? lv_color_hex(0x5865F2)
                : lv_color_hex(0x202225),
            LV_PART_MAIN
        );
        lv_obj_set_style_bg_color(
            mixerBars_[row],
            state_.mixerMuted[mixerIndex]
                ? lv_color_hex(0xED4245)
                : lv_color_hex(0x5865F2),
            LV_PART_INDICATOR
        );
    }
}


void SpotifyUI::updateNativeDiscord()
{
    if (discordPanel_ == nullptr)
    {
        return;
    }

    lv_label_set_text(
        discordChannelLabel_,
        state_.queueSource.isEmpty()
            ? "No Discord channel"
            : state_.queueSource.c_str()
    );

    for (uint8_t row = 0; row < 6; ++row)
    {
        if (row < state_.queueCount)
        {
            lv_label_set_text(
                discordMessageRows_[row],
                state_.queueEntries[row].c_str()
            );
        }
        else
        {
            lv_label_set_text(
                discordMessageRows_[row],
                ""
            );
        }
    }

    lv_label_set_text(
        discordPageMuteLabel_,
        state_.discordMuted ? "Unmute" : "Mute"
    );
    lv_label_set_text(
        discordPageDeafenLabel_,
        state_.discordDeafened ? "Undeafen" : "Deafen"
    );
    lv_obj_center(discordPageMuteLabel_);
    lv_obj_center(discordPageDeafenLabel_);

    const lv_color_t activeColor = lv_color_hex(0x5865F2);
    const lv_color_t warningColor = lv_color_hex(0xDA373C);
    const lv_color_t disabledColor = lv_color_hex(0x4E5058);

    lv_obj_set_style_bg_color(
        discordPageMuteButton_,
        !state_.discordCallActive
            ? disabledColor
            : (state_.discordMuted ? warningColor : activeColor),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_color(
        discordPageDeafenButton_,
        !state_.discordCallActive
            ? disabledColor
            : (state_.discordDeafened ? warningColor : activeColor),
        LV_PART_MAIN
    );

    if (state_.discordCallActive)
    {
        lv_obj_clear_state(
            discordPageMuteButton_,
            LV_STATE_DISABLED
        );
        lv_obj_clear_state(
            discordPageDeafenButton_,
            LV_STATE_DISABLED
        );
    }
    else
    {
        lv_obj_add_state(
            discordPageMuteButton_,
            LV_STATE_DISABLED
        );
        lv_obj_add_state(
            discordPageDeafenButton_,
            LV_STATE_DISABLED
        );
    }
}
