#include <Arduino.h>

#include "LovyanGFX_Driver.h"
#include "DisplayManager.h"
#include "SpotifyUI.h"
#include "Artwork.h"
#include "MetadataImage.h"
#include "SourceImage.h"
#include "ViewImage.h"
#include "BackgroundImage.h"
#include "Protocol.h"

LGFX gfx;

DisplayManager display;
SpotifyUI spotifyUi;
Artwork artwork;
MetadataImage metadataImage;
SourceImage sourceImage;
ViewImage viewImage;
BackgroundImage backgroundImage;
Protocol protocol(
    spotifyUi,
    artwork,
    metadataImage,
    sourceImage,
    viewImage,
    backgroundImage
);

void setup()
{
    Serial.setRxBufferSize(262144);
    Serial.begin(2000000);
    delay(500);

    if (!display.begin())
    {
        Serial.println("Display initialization failed.");

        while (true)
        {
            delay(1000);
        }
    }

    spotifyUi.create(lv_scr_act());
    spotifyUi.attachArtwork(artwork);
    spotifyUi.attachMetadataImage(metadataImage);
    spotifyUi.attachSourceImage(sourceImage);
    spotifyUi.attachViewImage(viewImage);
    spotifyUi.attachBackgroundImage(backgroundImage);

    Serial.println(
        "{\"type\":\"ready\",\"protocol\":2,"
        "\"metadata_image\":true,\"baud\":2000000}"
    );
}

void loop()
{
    protocol.poll();
    backgroundImage.applyPending();
    const bool viewApplied = viewImage.applyPending();
    spotifyUi.updateProgress();
    display.update();
    if (viewApplied)
    {
        Serial.println(
            "{\"type\":\"event\",\"event\":\"view_applied\"}"
        );
    }
    delay(1);
}
