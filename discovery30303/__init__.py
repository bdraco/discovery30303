import asyncio
import logging
import socket
import time
from typing import Callable, Dict, List, Optional, Tuple

from .base_device import BaseDevice30303, Device30303, normalize_mac
from .devices import (
    DEVICE_HANDLERS,
    MODEL_550,
    MODEL_550_PREFIX,
    Steamist450Device,
    Steamist550Device,
)

_LOGGER = logging.getLogger(__name__)

__version__ = "0.3.3"


MAX_UPDATES_WITHOUT_RESPONSE = 4


def create_udp_socket(discovery_port: int) -> socket.socket:
    """Create a udp socket used for communicating with the device."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    try:
        # Legacy devices require source port to be the discovery port
        sock.bind(("", discovery_port))
    except OSError as err:
        _LOGGER.debug("Port %s is not available: %s", discovery_port, err)
        sock.bind(("", 0))
    sock.setblocking(False)
    return sock


class Discovery30303(asyncio.DatagramProtocol):
    def __init__(
        self,
        destination: Tuple[str, int],
        on_response: Callable[[bytes, Tuple[str, int]], None],
    ) -> None:
        self.transport = None
        self.destination = destination
        self.on_response = on_response

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        """Trigger on_response."""
        self.on_response(data, addr)

    def error_received(self, ex: Optional[Exception]) -> None:
        """Handle error."""
        _LOGGER.error("Discovery30303 error: %s", ex)

    def connection_lost(self, ex: Optional[Exception]) -> None:
        """Do nothing on connection lost."""


class AIODiscovery30303:
    """A 30303 discovery scanner."""

    DISCOVERY_PORT = 30303
    BROADCAST_FREQUENCY = 3
    RESPONSE_SIZE = 64
    DISCOVER_MESSAGE = Steamist450Device.DISCOVER_MESSAGE
    DISCOVER_MESSAGES = tuple(handler.DISCOVER_MESSAGE for handler in DEVICE_HANDLERS)
    BROADCAST_ADDRESS = "<broadcast>"

    def __init__(self) -> None:
        self.found_devices: List[Device30303] = []

    def _destination_from_address(self, address: Optional[str]) -> Tuple[str, int]:
        if address is None:
            address = self.BROADCAST_ADDRESS
        return (address, self.DISCOVERY_PORT)

    def _process_response(
        self,
        data: Optional[bytes],
        from_address: Tuple[str, int],
        address: Optional[str],
        response_list: Dict[Tuple[str, int], Device30303],
    ) -> bool:
        """Process a response.

        Returns True if processing should stop
        """
        if data is None or data in self.DISCOVER_MESSAGES:
            return False
        if from_address in response_list:
            return False
        for handler in DEVICE_HANDLERS:
            if device := handler.parse_response(data, from_address):
                response_list[from_address] = device
                return from_address[0] == address
        return False

    def _send_discovery_messages(
        self,
        transport: asyncio.DatagramTransport,
        destination: Tuple[str, int],
    ) -> None:
        """Send all discovery messages to destination."""
        for message in self.DISCOVER_MESSAGES:
            _LOGGER.debug("discover: %s => %s", destination, message)
            transport.sendto(message, destination)

    async def _async_run_scan(
        self,
        transport: asyncio.DatagramTransport,
        destination: Tuple[str, int],
        timeout: int,
        found_all_future: "asyncio.Future[bool]",
    ) -> None:
        """Send the scans."""
        self._send_discovery_messages(transport, destination)
        quit_time = time.monotonic() + timeout
        remain_time = timeout
        while True:
            time_out = min(remain_time, timeout / self.BROADCAST_FREQUENCY)
            if time_out <= 0:
                return
            try:
                await asyncio.wait_for(
                    asyncio.shield(found_all_future), timeout=time_out
                )
            except asyncio.TimeoutError:
                if time.monotonic() >= quit_time:
                    return
                # No response, send broadcast again in case it got lost
                self._send_discovery_messages(transport, destination)
            else:
                return  # found_all
            remain_time = quit_time - time.monotonic()

    async def async_scan(
        self, timeout: int = 10, address: Optional[str] = None
    ) -> List[Device30303]:
        """Discover on port 30303."""
        sock = create_udp_socket(self.DISCOVERY_PORT)
        destination = self._destination_from_address(address)
        found_all_future: asyncio.Future[bool] = asyncio.Future()
        response_list: Dict[Tuple[str, int], Device30303] = {}

        def _on_response(data: bytes, addr: Tuple[str, int]) -> None:
            _LOGGER.debug("discover: %s <= %s", addr, data)
            if self._process_response(data, addr, address, response_list):
                if not found_all_future.done():
                    found_all_future.set_result(True)

        transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            lambda: Discovery30303(
                destination=destination,
                on_response=_on_response,
            ),
            sock=sock,
        )
        try:
            await self._async_run_scan(
                transport, destination, timeout, found_all_future
            )
        finally:
            transport.close()

        self.found_devices = list(response_list.values())
        return self.found_devices


__all__ = [
    "AIODiscovery30303",
    "BaseDevice30303",
    "DEVICE_HANDLERS",
    "Device30303",
    "Discovery30303",
    "MODEL_550",
    "MODEL_550_PREFIX",
    "Steamist450Device",
    "Steamist550Device",
    "create_udp_socket",
    "normalize_mac",
]
