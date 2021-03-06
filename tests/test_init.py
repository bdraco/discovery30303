import asyncio
import contextlib
from unittest.mock import MagicMock, patch

import pytest

from discovery30303 import (
    AIODiscovery30303,
    Device30303,
    Discovery30303,
    create_udp_socket,
)


@pytest.fixture
async def mock_discovery_aio_protocol():
    """Fixture to mock an asyncio connection."""
    loop = asyncio.get_running_loop()
    future = asyncio.Future()

    async def _wait_for_connection():
        transport, protocol = await future
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        return transport, protocol

    async def _mock_create_datagram_endpoint(func, sock=None):
        protocol: Discovery30303 = func()
        transport = MagicMock()
        protocol.connection_made(transport)
        with contextlib.suppress(asyncio.InvalidStateError):
            future.set_result((transport, protocol))
        return transport, protocol

    with patch.object(loop, "create_datagram_endpoint", _mock_create_datagram_endpoint):
        yield _wait_for_connection


@pytest.mark.asyncio
async def test_async_scanner_specific_address(mock_discovery_aio_protocol):
    """Test scanner with a specific address."""
    scanner = AIODiscovery30303()

    task = asyncio.ensure_future(
        scanner.async_scan(timeout=10, address="192.168.213.252")
    )
    _, protocol = await mock_discovery_aio_protocol()
    protocol.datagram_received(
        b"MY450-6340     \r\n00-1E-C0-38-63-40\r\nMaster Bath\x00   \x00",
        ("192.168.213.252", 48899),
    )
    await task
    assert scanner.found_devices == [
        Device30303(
            hostname="MY450-6340",
            ipaddress="192.168.213.252",
            mac="00:1E:C0:38:63:40",
            name="Master Bath",
        )
    ]


@pytest.mark.asyncio
async def test_async_scanner_broadcast(mock_discovery_aio_protocol):
    """Test scanner with a broadcast."""
    scanner = AIODiscovery30303()

    task = asyncio.ensure_future(scanner.async_scan(timeout=0.01))
    _, protocol = await mock_discovery_aio_protocol()
    protocol.datagram_received(
        b"MY450-6340     \r\n00-1E-C0-38-63-40\r\nMaster Bath\x00   \x00",
        ("192.168.213.252", 48899),
    )
    await task
    assert scanner.found_devices == [
        Device30303(
            hostname="MY450-6340",
            ipaddress="192.168.213.252",
            mac="00:1E:C0:38:63:40",
            name="Master Bath",
        )
    ]


@pytest.mark.asyncio
async def test_async_scanner_falls_back_to_any_source_port_if_socket_in_use():
    """Test port fallback."""
    hold_socket = create_udp_socket(AIODiscovery30303.DISCOVERY_PORT)
    assert hold_socket.getsockname() == ("0.0.0.0", 30303)
    random_socket = create_udp_socket(AIODiscovery30303.DISCOVERY_PORT)
    assert random_socket.getsockname() != ("0.0.0.0", 30303)
