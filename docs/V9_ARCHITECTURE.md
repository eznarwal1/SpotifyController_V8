# Universal Media Controller V9

V9 moves the Queue, Mixer, and Notifications pages from streamed RGB565 page
images to native LVGL widgets on the ESP32.

## Migration rule

Each V9 milestone must preserve the existing V8 behavior until its replacement
has been tested on the physical display.

## Planned modules

### Companion

- `companion/v9/queue_model.py`: source-independent queue data model.
- Later: queue collection, mixer collection, notifications, and structured
  serial messages.

### Firmware

- `src/v9/`: native LVGL screens and widgets.
- Existing V8 files remain active during the migration.

## Milestones

1. V9.01: organization scaffold and queue model.
2. V9.02: structured queue model and state fields.
3. V9.03: native LVGL Queue page connected to live browser queue data.
4. V9.04: native LVGL Mixer page.
5. V9.05: native Notifications page.

V9.03 replaces the streamed Queue bitmap with native LVGL labels. The
existing bitmap renderer remains active for Mixer, Notifications, and Themes.
Album artwork and the blurred background continue to use the existing image
transport.

## V9.04

The Mixer page is now rendered with native LVGL labels and bars. The PC sends
only application names, volume percentages, mute states, and the selected row.
Notifications and Themes remain on the legacy bitmap renderer.
