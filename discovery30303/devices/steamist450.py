"""Steamist TSC-450 (and Microchip TCP/IP stack) device discovery handler."""

from typing import Optional, Tuple

from ..base_device import BaseDevice30303, Device30303, normalize_mac


class Steamist450Device(BaseDevice30303):
    """Protocol handler for Steamist 450 and legacy 30303 devices."""

    DISCOVER_MESSAGE = b"Discovery: Who is out there?"

    @classmethod
    def parse_response(
        cls, data: bytes, from_address: Tuple[str, int]
    ) -> Optional[Device30303]:
        """Parse a CRLF-delimited 30303 discovery response."""
        if data == cls.DISCOVER_MESSAGE:
            return None
        try:
            decoded = data.decode("utf-8")
        except UnicodeDecodeError:
            return None
        data_split = decoded.split("\r\n")
        if len(data_split) < 3:
            return None
        hostname = data_split[0].rstrip()
        model = hostname.split("-", maxsplit=1)[0] if "-" in hostname else None
        return Device30303(
            hostname=hostname,
            ipaddress=from_address[0],
            mac=normalize_mac(data_split[1].rstrip()),
            name=data_split[2].split("\x00")[0].rstrip(),
            model=model,
            raw_data=data,
        )
