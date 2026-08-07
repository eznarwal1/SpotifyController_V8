#pragma once

#include <Arduino.h>
#include <lvgl.h>

#include "AppState.h"
#include "Artwork.h"
#include "MetadataImage.h"
#include "SourceImage.h"
#include "ViewImage.h"
#include "BackgroundImage.h"

class SpotifyUI
{
public:
    SpotifyUI();

    void create(lv_obj_t* screen);
    void applyState(const AppState& state);
    void updateProgress();
    void attachArtwork(Artwork& artwork);
    void attachMetadataImage(MetadataImage& metadataImage);
    void attachSourceImage(SourceImage& sourceImage);
    void attachViewImage(ViewImage& viewImage);
    void attachBackgroundImage(BackgroundImage& backgroundImage);

private:
    static void playPauseEvent(lv_event_t* event);
    static void previousEvent(lv_event_t* event);
    static void nextEvent(lv_event_t* event);
    static void sourceEvent(lv_event_t* event);
    static void discordMuteEvent(lv_event_t* event);
    static void discordDeafenEvent(lv_event_t* event);
    static void viewEvent(lv_event_t* event);
    static void utilityPreviousEvent(lv_event_t* event);
    static void utilitySelectEvent(lv_event_t* event);
    static void utilityNextEvent(lv_event_t* event);
    static void queueHomeEvent(lv_event_t* event);
    static void mixerDownEvent(lv_event_t* event);
    static void mixerMuteEvent(lv_event_t* event);
    static void mixerUpEvent(lv_event_t* event);

    void updatePlayPauseIcon(bool playing);
    void updateModeIndicators();
    void updateSourceButton();
    void updateStatusArea();
    void updateNativeQueue();
    void updateNativeMixer();
    void updatePageVisibility();
    static void setObjectVisible(lv_obj_t* object, bool visible);
    void setPlayPending(bool pending);
    void updateProgressNow(bool force);
    static void formatTime(
        uint32_t milliseconds,
        char* output,
        size_t outputSize
    );

    lv_obj_t* title_;
    lv_obj_t* artist_;
    lv_obj_t* album_;
    lv_obj_t* previousButton_;
    lv_obj_t* playButton_;
    lv_obj_t* playLabel_;
    lv_obj_t* nextButton_;
    lv_obj_t* progressBar_;
    lv_obj_t* elapsed_;
    lv_obj_t* duration_;
    lv_obj_t* artworkContainer_;
    lv_obj_t* artworkImage_;
    lv_obj_t* artworkText_;
    lv_obj_t* shuffleLabel_;
    lv_obj_t* repeatLabel_;
    lv_obj_t* sourceButton_;
    lv_obj_t* metadataImageObject_;
    lv_obj_t* sourceLabel_;
    lv_obj_t* sourceImageObject_;
    lv_obj_t* voiceStatusDot_;
    lv_obj_t* statusLabel_;
    lv_obj_t* batteryLabel_;

    lv_obj_t* discordMuteButton_;
    lv_obj_t* discordMuteLabel_;
    lv_obj_t* micIconContainer_;
    lv_obj_t* micBody_;
    lv_obj_t* micBracket_;
    lv_obj_t* micStem_;
    lv_obj_t* micBase_;
    lv_obj_t* micSlash_;

    lv_obj_t* discordDeafenButton_;
    lv_obj_t* discordDeafenLabel_;
    lv_obj_t* headphoneIconContainer_;
    lv_obj_t* headphoneArc_;
    lv_obj_t* headphoneLeft_;
    lv_obj_t* headphoneRight_;
    lv_obj_t* headphoneSlash_;
    lv_obj_t* viewButton_;
    lv_obj_t* viewLabel_;
    lv_obj_t* viewImageObject_;
    lv_obj_t* backgroundImageObject_;
    lv_obj_t* queuePanel_;
    lv_obj_t* queueHeading_;
    lv_obj_t* queueSourceLabel_;
    lv_obj_t* queueRows_[4];
    lv_obj_t* mixerPanel_;
    lv_obj_t* mixerHeading_;
    lv_obj_t* mixerRows_[4];
    lv_obj_t* mixerBars_[4];
    lv_obj_t* utilityPreviousButton_;
    lv_obj_t* utilityPreviousLabel_;
    lv_obj_t* utilitySelectButton_;
    lv_obj_t* utilitySelectLabel_;
    lv_obj_t* utilityNextButton_;
    lv_obj_t* utilityNextLabel_;
    lv_obj_t* queueHomeButton_;
    lv_obj_t* queueHomeLabel_;
    lv_obj_t* mixerDownButton_;
    lv_obj_t* mixerDownLabel_;
    lv_obj_t* mixerMuteButton_;
    lv_obj_t* mixerMuteLabel_;
    lv_obj_t* mixerUpButton_;
    lv_obj_t* mixerUpLabel_;
    lv_obj_t* notificationBanner_;

    bool displayedPlaying_;
    bool playPending_;
    bool expectedPlaying_;
    uint32_t playStartedAtMs_;
    uint32_t lastProgressUpdateMs_;
    AppState state_;

    static SpotifyUI* instance_;
};
