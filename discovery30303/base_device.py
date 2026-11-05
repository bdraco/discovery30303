"""Base device definition for discovery30303."""

from dataclasses import dataclass
from typing import Any, ClassVar, Dict, Optional, Tuple


def normalize_mac(mac: str) -> str:
    """Normalize a MAC address to colon-separated hex."""
    return ":".join([i.zfill(2) for i in mac.replace("-", ":").split(":")])


@dataclass
class Device30303:
    """A device discovered via port 30303."""

    hostname: str
    mac: str
    ipaddress: str
    name: str
    model: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None
    raw_data: Optional[bytes] = None


class BaseDevice30303:
    """Base protocol handler for a port 30303 device."""

    DISCOVER_MESSAGE: ClassVar[bytes]

    @classmethod
    def parse_response(
        cls, data: bytes, from_address: Tuple[str, int]
    ) -> Optional[Device30303]:
        """Parse a discovery response packet into a Device30303 if it matches."""
        raise NotImplementedError
