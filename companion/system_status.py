from __future__ import annotations

from dataclasses import dataclass

import psutil


@dataclass(slots=True)
class BatteryStatus:
    present: bool = False
    percent: int = 0
    charging: bool = False

def get_battery_status() -> BatteryStatus:
    try:
        battery = psutil.sensors_battery()
    except Exception as exc:
        # psutil may raise if sensors are not available on this platform
        import logging

        logging.debug("get_battery_status: sensors_battery failed: %s", exc)
        battery = None
    if battery is None:
        return BatteryStatus()
    return BatteryStatus(
        present=True,
        percent=max(0, min(100, round(float(battery.percent)))),
        charging=bool(battery.power_plugged),
    )
