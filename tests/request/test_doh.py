from async_dns.resolver import ProxyResolver
import unittest

from async_dns.core import Address, DNSMessage, REQUEST, Record, types
from async_dns.request import doh, util
from async_dns.request.doh import client
from tests.util import async_test

from .util import MockConnection, MockConnectionHandle


class TestDoH(unittest.TestCase):
    def setUp(self):
        self._conn = MockConnection()
        MockConnectionHandle.conn = self._conn
        client.ConnectionHandle = MockConnectionHandle
        resolver = ProxyResolver()
        resolver.cache.add('dns.alidns.com', types.A, ['127.0.0.1'])
        doh.set_client(client.DoHClient(resolver))

    def tearDown(self):
        client.ConnectionHandle = util.ConnectionHandle

    @async_test
    async def test_doh(self):
        req = DNSMessage(qr=REQUEST)
        req.qd = [Record(REQUEST, 'www.google.com', types.A)]
        raw = b'\x02\x9a\x01 \x00\x01\x00\x00\x00\x00\x00\x01\x03www\x05baidu\x03com\x00\x00\x01\x00\x01\x00\x00)\x10\x00\x00\x00\x00\x00\x00\x00'
        self._conn.reader.feed(b'HTTP/1.1 200 OK\n')
        self._conn.reader.feed(f'content-length: {len(raw)}\n'.encode())
        self._conn.reader.feed(b'\n')
        self._conn.reader.feed(raw)
        msg = await doh.request(
            req,
            Address.parse('https://dns.alidns.com/dns-query',
                          allow_domain=True))
        self.assertEqual(msg.qd[0].name, 'www.baidu.com')
        self.assertEqual(
            self._conn.writer.buffer.getvalue(),
            b'GET /dns-query?dns=AAABgAABAAAAAAAAA3d3dwZnb29nbGUDY29tAAABAAE HTTP/1.1\r\nhost: dns.alidns.com\r\naccept: application/dns-message\r\ncontent-type: application/dns-message\r\n\r\n'
        )
