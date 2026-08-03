"""V9 companion modules.

These modules are introduced incrementally and are not imported by the V8
runtime until the corresponding V9 milestone is tested.
"""

from .queue_model import QueueEntry, normalize_queue_entries

__all__ = ["QueueEntry", "normalize_queue_entries"]
