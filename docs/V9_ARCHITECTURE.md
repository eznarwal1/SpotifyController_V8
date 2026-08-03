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
2. V9.02: structured queue message.
3. V9.03: native LVGL Queue page.
4. V9.04: native LVGL Mixer page.
5. V9.05: native Notifications page.

This document is intentionally descriptive only. V9.01 does not change the
running companion or firmware.
