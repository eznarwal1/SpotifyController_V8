from __future__ import annotations

from pycaw.pycaw import AudioUtilities


class VolumeController:
    """Read and control the Windows master output volume."""

    def __init__(self) -> None:
        device = AudioUtilities.GetSpeakers()
        self._volume = device.EndpointVolume

    def get_volume(self) -> int:
        """Return the current master volume as an integer from 0 to 100."""
        scalar = self._volume.GetMasterVolumeLevelScalar()
        return round(scalar * 100)

    def set_volume(self, volume: int) -> None:
        """Set the master volume."""
        volume = max(0, min(100, volume))

        self._volume.SetMasterVolumeLevelScalar(
            volume / 100.0,
            None,
        )

    def change_volume(self, amount: int) -> None:
        """Increase or decrease the master volume."""
        self.set_volume(self.get_volume() + amount)

    def is_muted(self) -> bool:
        """Return True if Windows is muted."""
        return bool(self._volume.GetMute())

    def toggle_mute(self) -> None:
        """Toggle the mute state."""
        self._volume.SetMute(
            not self.is_muted(),
            None,
        )