from __future__ import annotations

from dataclasses import dataclass
import psutil


@dataclass(slots=True)
class DashboardSnapshot:
    cpu_percent: int
    memory_percent: int
    battery_text: str
    network_text: str


_last_net = None


def snapshot(
    battery_present: bool,
    battery_percent: int,
    battery_charging: bool,
) -> DashboardSnapshot:
    global _last_net

    cpu = round(psutil.cpu_percent(interval=None))
    memory = round(psutil.virtual_memory().percent)

    if battery_present:
        battery = f"{battery_percent}%"
        if battery_charging:
            battery += " charging"
    else:
        battery = "Desktop power"

    counters = psutil.net_io_counters()
    if _last_net is None:
        network = "Network active"
    else:
        sent = max(0, counters.bytes_sent - _last_net.bytes_sent)
        received = max(0, counters.bytes_recv - _last_net.bytes_recv)
        network = f"Net ↓{received // 1024} KB  ↑{sent // 1024} KB"
    _last_net = counters

    return DashboardSnapshot(
        cpu_percent=cpu,
        memory_percent=memory,
        battery_text=battery,
        network_text=network,
    )
