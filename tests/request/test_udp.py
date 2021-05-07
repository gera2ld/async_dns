import asyncio
import unittest
from ..util import async_test
from async_dns.core import DNSMessage, Record, REQUEST, Address, types
from async_dns.request.udp import Dispatcher, request


class MockTransport:
    def __init__(self):
        self.data = []
        self.input = []

    def feed(self, data):
        self.input.append(data)

    def sendto(self, data, addr):
        self.data.append((data, addr))


class MockRandId:
    def get(self):
        return 666

    def put(self, data):
        pass


class TestUDP(unittest.TestCase):
    def setUp(self):
        loop = asyncio.get_event_loop()
        self._create_datagram_endpoint = loop.create_datagram_endpoint
        _dispatcher_initialize = Dispatcher.initialize
        self._dispatcher_initialize = _dispatcher_initialize
        self._mock_transport = MockTransport()

        async def mock_create_datagram_endpoint(Protocol, *k, **kw):
            protocol = Protocol()
            protocol.connection_made(self._mock_transport)

            def feed_data():
                for chunk in self._mock_transport.input:
                    protocol.datagram_received(chunk, None)

            loop.call_soon(feed_data)
            return self._mock_transport, protocol

        loop.create_datagram_endpoint = mock_create_datagram_endpoint

        async def initialize(self):
            self.rand_id = MockRandId()
            return await _dispatcher_initialize(self)

        Dispatcher.initialize = initialize
        Dispatcher.data.clear()

    def tearDown(self):
        loop = asyncio.get_event_loop()
        loop.create_datagram_endpoint = self._create_datagram_endpoint
        Dispatcher.initialize = self._dispatcher_initialize
        Dispatcher.data.clear()

    @async_test
    async def test_udp(self):
        req = DNSMessage(qr=REQUEST, qid=MockRandId().get())
        req.qd = [Record(REQUEST, 'www.google.com', types.A)]
        self._mock_transport.feed(
            b'\x02\x9a\x01 \x00\x01\x00\x00\x00\x00\x00\x01\x03www\x05baidu\x03com\x00\x00\x01\x00\x01\x00\x00)\x10\x00\x00\x00\x00\x00\x00\x00'
        )
        msg = await request(req, Address.parse('udp://114.114.114.114'))
        self.assertEqual(msg.qd[0].name, 'www.baidu.com')
        self.assertEqual(self._mock_transport.data, [(
            b'\x02\x9a\x01\x80\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x06google\x03com\x00\x00\x01\x00\x01',
            ('114.114.114.114', 53))])
