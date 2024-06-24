import asyncio
import logging
import socket
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

_LOGGER = logging.getLogger(__name__)

__version__ = "0.3.2"


MAX_UPDATES_WITHOUT_RESPONSE = 4


@dataclass
class Device30303:
    """A device discovered via port 30303."""

    hostname: str
    mac: str
    ipaddress: str
    name: str


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


def normalize_mac(mac: str) -> str:
    return ":".join([i.zfill(2) for i in mac.replace("-", ":").split(":")])


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
    DISCOVER_MESSAGE = b"Discovery: Who is out there?"
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
        response_list: Dict[str, Device30303],
    ) -> bool:
        """Process a response.

        Returns True if processing should stop
        """
        if data is None or data == self.DISCOVER_MESSAGE:
            return
        data_split = data.decode("utf-8").split("\r\n")
        if len(data_split) < 3 or from_address[0] in response_list:
            return
        response_list[from_address] = Device30303(
            hostname=data_split[0].rstrip(),
            ipaddress=from_address[0],
            mac=normalize_mac(data_split[1].rstrip()),
            name=data_split[2].split("\x00")[0].rstrip(),
        )
        return from_address[0] == address

    async def _async_run_scan(
        self,
        transport: asyncio.DatagramTransport,
        destination: Tuple[str, int],
        timeout: int,
        found_all_future: "asyncio.Future[bool]",
    ) -> None:
        """Send the scans."""
        _LOGGER.debug("discover: %s => %s", destination, self.DISCOVER_MESSAGE)
        transport.sendto(self.DISCOVER_MESSAGE, destination)
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
                # No response, send broadcast again in cast it got lost
                _LOGGER.debug("discover: %s => %s", destination, self.DISCOVER_MESSAGE)
                transport.sendto(self.DISCOVER_MESSAGE, destination)
            else:
                return  # found_all
            remain_time = quit_time - time.monotonic()

    async def async_scan(
        self, timeout: int = 10, address: Optional[str] = None
    ) -> List[Device30303]:
        """Discover on port 30303."""
        sock = create_udp_socket(self.DISCOVERY_PORT)
        destination = self._destination_from_address(address)
        found_all_future = asyncio.Future()
        response_list = {}

        def _on_response(data: bytes, addr: Tuple[str, int]) -> None:
            _LOGGER.debug("discover: %s <= %s", addr, data)
            if self._process_response(data, addr, address, response_list):
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
