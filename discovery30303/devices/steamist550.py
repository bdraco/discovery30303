"""Steamist TSC-550 device discovery handler."""

from typing import Any, Dict, Optional, Tuple

from ..base_device import BaseDevice30303, Device30303, normalize_mac

MODEL_550_PREFIX = b"STM 550"
MODEL_550 = "MY550"


class Steamist550Device(BaseDevice30303):
    """Protocol handler for Steamist TSC-550 devices."""

    DISCOVER_MESSAGE = b"stdisc"

    @classmethod
    def parse_response(
        cls, data: bytes, from_address: Tuple[str, int]
    ) -> Optional[Device30303]:
        """Parse a Steamist TSC-550 UDP response."""
        if data == cls.DISCOVER_MESSAGE or not data.startswith(MODEL_550_PREFIX):
            return None
        if len(data) < 34:
            return None
        try:
            temp_str = data[7:10].decode("utf-8").strip()
            temp = int(temp_str) if temp_str else None
            temp_units = data[10:11].decode("utf-8")
            profile = int(data[11:12].decode("utf-8"))
            minutes_str = data[12:14].decode("utf-8").strip()
            minutes_remain = int(minutes_str) if minutes_str else 0
            seconds_str = data[14:16].decode("utf-8").strip()
            seconds_remain = int(seconds_str) if seconds_str else 0
            mac = normalize_mac(data[16:33].decode("utf-8").strip())
            name = data[33:].split(b"\x00")[0].decode("utf-8").rstrip()
        except (UnicodeDecodeError, ValueError):
            return None

        mac_suffix = mac.replace(":", "")[-4:].upper()
        hostname = f"{MODEL_550}-{mac_suffix}"
        additional_data: Dict[str, Any] = {
            "temperature": temp,
            "temp_units": temp_units,
            "profile": profile,
            "minutes_remain": minutes_remain,
            "seconds_remain": seconds_remain,
        }
        return Device30303(
            hostname=hostname,
            ipaddress=from_address[0],
            mac=mac,
            name=name,
            model=MODEL_550,
            additional_data=additional_data,
            raw_data=data,
        )
