import struct
import unittest

from async_dns.core import Address, DNSMessage, REQUEST, Record, types
from async_dns.request import tcp, util
from tests.util import async_test

from .util import MockConnection, MockConnectionHandle


class TestTCP(unittest.TestCase):
    def setUp(self):
        self._conn = MockConnection()
        MockConnectionHandle.conn = self._conn
        tcp.ConnectionHandle = MockConnectionHandle

    def tearDown(self):
        tcp.ConnectionHandle = util.ConnectionHandle

    @async_test
    async def test_tcp(self):
        req = DNSMessage(qr=REQUEST)
        req.qd = [Record(REQUEST, 'www.google.com', types.A)]
        raw = b'\x02\x9a\x01 \x00\x01\x00\x00\x00\x00\x00\x01\x03www\x05baidu\x03com\x00\x00\x01\x00\x01\x00\x00)\x10\x00\x00\x00\x00\x00\x00\x00'
        self._conn.reader.feed(struct.pack('!H', len(raw)))
        self._conn.reader.feed(raw)
        msg = await tcp.request(req, Address.parse('tcp://114.114.114.114'))
        self.assertEqual(msg.qd[0].name, 'www.baidu.com')
        self.assertEqual(self._conn.writer.buffer.getvalue(), b'\x00 \x00\x00\x01\x80\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x06google\x03com\x00\x00\x01\x00\x01')
