"""Device handlers for discovery30303."""

from typing import List, Type

from ..base_device import BaseDevice30303
from .steamist450 import Steamist450Device
from .steamist550 import MODEL_550, MODEL_550_PREFIX, Steamist550Device

DEVICE_HANDLERS: List[Type[BaseDevice30303]] = [
    Steamist550Device,
    Steamist450Device,
]

__all__ = [
    "DEVICE_HANDLERS",
    "MODEL_550",
    "MODEL_550_PREFIX",
    "Steamist450Device",
    "Steamist550Device",
]
